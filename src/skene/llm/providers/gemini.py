"""
Google Gemini LLM client implementation.
"""

import asyncio
from functools import partial
from typing import AsyncGenerator, Optional

from loguru import logger
from pydantic import SecretStr

from skene.llm.base import LLMClient

# Default fallback model for rate limiting (429 errors)
# Using stable 2.5-flash as fallback (works with both v1 and v1beta APIs)
DEFAULT_FALLBACK_MODEL = "gemini-2.5-flash"

# Retry delays in seconds for no-fallback mode (exponential-ish backoff)
RETRY_DELAYS = [5, 15, 30]

DEFAULT_TIMEOUT = 900.0


def _extract_usage(response) -> dict[str, int] | None:
    """Extract token usage from a Gemini response's usage_metadata.

    The google-genai SDK exposes prompt_token_count, candidates_token_count,
    thoughts_token_count, cached_content_token_count, and total_token_count.
    We map these to the common interface (output_tokens / input_tokens) and
    include thoughts_tokens when the model used thinking.
    """
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return None
    prompt = getattr(meta, "prompt_token_count", None)
    candidates = getattr(meta, "candidates_token_count", None)
    if prompt is None or candidates is None:
        return None
    usage: dict[str, int] = {
        "output_tokens": candidates,
        "input_tokens": prompt,
    }
    thoughts = getattr(meta, "thoughts_token_count", None)
    if thoughts:
        usage["thoughts_tokens"] = thoughts
    cached = getattr(meta, "cached_content_token_count", None)
    if cached:
        usage["cached_tokens"] = cached
    return usage


class GoogleGeminiClient(LLMClient):
    """
    Google Gemini LLM client.

    Handles rate limiting by automatically falling back to a secondary model
    when the primary model returns a 429 RESOURCE_EXHAUSTED error.

    Example:
        client = GoogleGeminiClient(
            api_key=SecretStr("your-api-key"),
            model_name="gemini-3-flash-preview"  # v1beta API requires -preview suffix
        )
        response = await client.generate_content("Hello!")
    """

    def __init__(
        self,
        api_key: SecretStr,
        model_name: str,
        fallback_model: Optional[str] = None,
        no_fallback: Optional[bool] = False,
    ):
        """
        Initialize the Gemini client.

        Args:
            api_key: Google API key (wrapped in SecretStr for security)
            model_name: Primary model to use (e.g., "gemini-3-flash-preview" for v1beta API)
            fallback_model: Model to use when rate limited (default: gemini-2.5-flash)
            no_fallback: When True, retry same model on 429 instead of falling back
        """
        try:
            from google import genai
        except ImportError:
            raise ImportError("google-genai is required for Gemini support. Install with: pip install skene[gemini]")

        self.api_key = api_key.get_secret_value()
        self.model_name = model_name
        self.fallback_model = fallback_model or DEFAULT_FALLBACK_MODEL
        self.no_fallback = no_fallback
        self.client = genai.Client(api_key=self.api_key)

    def _is_rate_limit_error(self, error: Exception) -> bool:
        """Check if the error is a 429 rate limit error."""
        error_str = str(error)
        return "429" in error_str and "RESOURCE_EXHAUSTED" in error_str

    async def _call_stream_api(self, model: str, prompt: str):
        """Start a blocking generate_content_stream call in a thread pool with timeout."""
        loop = asyncio.get_event_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self.client.models.generate_content_stream(model=model, contents=prompt),
                ),
                timeout=DEFAULT_TIMEOUT,
            )
        except asyncio.TimeoutError:
            raise RuntimeError(f"Google Gemini stream request timed out after {DEFAULT_TIMEOUT:.0f}s (model: {model})")

    async def _call_api(self, model: str, prompt: str):
        """Run a blocking generate_content call in a thread pool with timeout."""
        loop = asyncio.get_event_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    partial(self.client.models.generate_content, model=model, contents=prompt),
                ),
                timeout=DEFAULT_TIMEOUT,
            )
        except asyncio.TimeoutError:
            raise RuntimeError(f"Google Gemini request timed out after {DEFAULT_TIMEOUT:.0f}s (model: {model})")

    async def generate_content(
        self,
        prompt: str,
    ) -> str:
        content, _ = await self.generate_content_with_usage(prompt)
        return content

    async def generate_content_with_usage(
        self,
        prompt: str,
    ) -> tuple[str, dict[str, int] | None]:
        """Generate text and return (content, usage). Usage has output_tokens, input_tokens.
        Returns None when not in response."""
        try:
            response = await self._call_api(self.model_name, prompt)
            return (response.text.strip(), _extract_usage(response))
        except Exception as e:
            if self._is_rate_limit_error(e):
                if self.no_fallback:
                    content = await self._retry_with_backoff(prompt, stream=False)
                    return (content, None)
                logger.warning(
                    f"Rate limit (429) hit on model {self.model_name}, falling back to {self.fallback_model}"
                )
                try:
                    response = await self._call_api(self.fallback_model, prompt)
                    logger.info(f"Successfully generated content using fallback model {self.fallback_model}")
                    return (response.text.strip(), _extract_usage(response))
                except Exception as fallback_error:
                    raise RuntimeError(
                        f"Error calling Google Gemini (fallback model {self.fallback_model}): {fallback_error}"
                    )
            raise RuntimeError(f"Error calling Google Gemini: {e}")

    async def generate_content_stream(
        self,
        prompt: str,
    ) -> AsyncGenerator[str, None]:
        """
        Generate content with streaming.

        Automatically retries with fallback model on rate limit errors.

        Args:
            prompt: The prompt to send to the model

        Yields:
            Text chunks as they are generated

        Raises:
            RuntimeError: If streaming fails on both primary and fallback models
        """
        model_to_use = self.model_name
        try:
            response_stream = await self._call_stream_api(model_to_use, prompt)
            loop = asyncio.get_event_loop()

            def get_next_chunk(iterator):
                try:
                    return next(iterator), False
                except StopIteration:
                    return None, True

            chunk_iterator = iter(response_stream)
            while True:
                chunk, done = await loop.run_in_executor(None, get_next_chunk, chunk_iterator)
                if done:
                    break
                if chunk and hasattr(chunk, "text") and chunk.text:
                    yield chunk.text

        except Exception as e:
            if self._is_rate_limit_error(e) and self.no_fallback:
                async for chunk in self._retry_stream_with_backoff(prompt):
                    yield chunk
                return
            if self._is_rate_limit_error(e) and model_to_use == self.model_name:
                logger.warning(
                    f"Rate limit (429) hit on model {self.model_name} during streaming, "
                    f"falling back to {self.fallback_model}"
                )
                try:
                    response_stream = await self._call_stream_api(self.fallback_model, prompt)
                    loop = asyncio.get_event_loop()

                    def get_next_chunk(iterator):
                        try:
                            return next(iterator), False
                        except StopIteration:
                            return None, True

                    chunk_iterator = iter(response_stream)
                    logger.info(f"Successfully started streaming with fallback model {self.fallback_model}")
                    while True:
                        chunk, done = await loop.run_in_executor(None, get_next_chunk, chunk_iterator)
                        if done:
                            break
                        if chunk and hasattr(chunk, "text") and chunk.text:
                            yield chunk.text
                except Exception as fallback_error:
                    raise RuntimeError(
                        f"Error in streaming generation (fallback model {self.fallback_model}): {fallback_error}"
                    )
            else:
                raise RuntimeError(f"Error in streaming generation: {e}")

    async def _retry_with_backoff(self, prompt: str, stream: bool = False) -> str:
        """Retry the same model with exponential backoff on rate limit errors."""
        for attempt, delay in enumerate(RETRY_DELAYS, 1):
            logger.warning(f"Rate limit (429) on {self.model_name}, retry {attempt}/{len(RETRY_DELAYS)} in {delay}s")
            await asyncio.sleep(delay)
            try:
                response = await self._call_api(self.model_name, prompt)
                return response.text.strip()
            except Exception as retry_error:
                if not self._is_rate_limit_error(retry_error):
                    raise RuntimeError(f"Error calling Google Gemini: {retry_error}")
                continue
        raise RuntimeError(f"Rate limit on {self.model_name} after {len(RETRY_DELAYS)} retries")

    async def _retry_stream_with_backoff(self, prompt: str) -> AsyncGenerator[str, None]:
        """Retry streaming with the same model using exponential backoff."""
        for attempt, delay in enumerate(RETRY_DELAYS, 1):
            logger.warning(
                f"Rate limit (429) on {self.model_name} during streaming, "
                f"retry {attempt}/{len(RETRY_DELAYS)} in {delay}s"
            )
            await asyncio.sleep(delay)
            try:
                response_stream = await self._call_stream_api(self.model_name, prompt)
                loop = asyncio.get_event_loop()

                def get_next_chunk(iterator):
                    try:
                        return next(iterator), False
                    except StopIteration:
                        return None, True

                chunk_iterator = iter(response_stream)
                while True:
                    chunk, done = await loop.run_in_executor(None, get_next_chunk, chunk_iterator)
                    if done:
                        break
                    if chunk and hasattr(chunk, "text") and chunk.text:
                        yield chunk.text
                return
            except Exception as retry_error:
                if not self._is_rate_limit_error(retry_error):
                    raise RuntimeError(f"Error in streaming generation: {retry_error}")
                continue
        raise RuntimeError(f"Rate limit on {self.model_name} after {len(RETRY_DELAYS)} retries")

    def get_model_name(self) -> str:
        """Return the primary model name."""
        return self.model_name

    def get_provider_name(self) -> str:
        """Return the provider name."""
        return "google"
