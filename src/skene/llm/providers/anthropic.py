"""
Anthropic LLM client implementation.
"""

import asyncio
from typing import AsyncGenerator, Optional

from loguru import logger
from pydantic import SecretStr

from skene.llm.base import LLMClient

# Default fallback model for rate limiting (429 errors)
DEFAULT_FALLBACK_MODEL = "claude-haiku-4-5"

# Retry delays in seconds for no-fallback mode (exponential-ish backoff)
RETRY_DELAYS = [5, 15, 30]

DEFAULT_TIMEOUT = 900.0


class AnthropicClient(LLMClient):
    """
    Anthropic LLM client.

    Handles rate limiting by automatically falling back to a secondary model
    when the primary model returns a 429 rate limit error.

    Example:
        client = AnthropicClient(
            api_key=SecretStr("your-api-key"),
            model_name="claude-haiku-4-5-20251001"
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
        Initialize the Anthropic client.

        Args:
            api_key: Anthropic API key (wrapped in SecretStr for security)
            model_name: Primary model to use (e.g., "claude-haiku-4-5-20251001")
            fallback_model: Model to use when rate limited (default: claude-haiku-4-5-20251001)
            no_fallback: When True, retry same model on 429 instead of falling back
        """
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            raise ImportError("anthropic is required for Anthropic support. Install with: pip install skene[anthropic]")

        self.model_name = model_name
        self.fallback_model = fallback_model or DEFAULT_FALLBACK_MODEL
        self.no_fallback = no_fallback
        self.client = AsyncAnthropic(api_key=api_key.get_secret_value(), timeout=DEFAULT_TIMEOUT)

    async def generate_content(
        self,
        prompt: str,
    ) -> str:
        """
        Generate text from Anthropic.

        Automatically retries with fallback model on rate limit errors.

        Args:
            prompt: The prompt to send to the model

        Returns:
            Generated text as a string

        Raises:
            RuntimeError: If generation fails on both primary and fallback models
        """
        try:
            from anthropic import RateLimitError
        except ImportError:
            RateLimitError = Exception  # Fallback if import fails

        try:
            response = await self.client.messages.create(
                model=self.model_name,
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except RateLimitError as e:
            logger.warning(f"RateLimitError on {self.model_name}: {e}")
            if self.no_fallback:
                return await self._retry_with_backoff(prompt)
            logger.warning(f"Falling back to {self.fallback_model}")
            try:
                response = await self.client.messages.create(
                    model=self.fallback_model,
                    max_tokens=8192,
                    messages=[{"role": "user", "content": prompt}],
                )
                logger.info(f"Successfully generated content using fallback model {self.fallback_model}")
                return response.content[0].text.strip()
            except Exception as fallback_error:
                raise RuntimeError(f"Error calling Anthropic (fallback model {self.fallback_model}): {fallback_error}")
        except Exception as e:
            raise RuntimeError(f"Error calling Anthropic: {e}")

    async def generate_content_with_usage(
        self,
        prompt: str,
    ) -> tuple[str, dict[str, int] | None]:
        """Generate text and return (content, usage). Usage has output_tokens, input_tokens. Returns None when not in response."""
        try:
            from anthropic import RateLimitError
        except ImportError:
            class FallbackRateLimitError(Exception):
                """Fallback error used when anthropic.RateLimitError is unavailable."""
                pass

            RateLimitError = FallbackRateLimitError

        def _usage_from_response(response) -> dict[str, int] | None:
            usage = getattr(response, "usage", None)
            if usage and hasattr(usage, "input_tokens") and hasattr(usage, "output_tokens"):
                return {"output_tokens": usage.output_tokens, "input_tokens": usage.input_tokens}
            return None

        try:
            response = await self.client.messages.create(
                model=self.model_name,
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}],
            )
            return (response.content[0].text.strip(), _usage_from_response(response))
        except RateLimitError as e:
            logger.warning(f"RateLimitError on {self.model_name}: {e}")
            if self.no_fallback:
                content = await self._retry_with_backoff(prompt)
                return (content, None)
            logger.warning(f"Falling back to {self.fallback_model}")
            try:
                response = await self.client.messages.create(
                    model=self.fallback_model,
                    max_tokens=8192,
                    messages=[{"role": "user", "content": prompt}],
                )
                logger.info(f"Successfully generated content using fallback model {self.fallback_model}")
                return (response.content[0].text.strip(), _usage_from_response(response))
            except Exception as fallback_error:
                raise RuntimeError(
                    f"Error calling Anthropic (fallback model {self.fallback_model}): {fallback_error}"
                )
        except Exception as e:
            raise RuntimeError(f"Error calling Anthropic: {e}")

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
        try:
            from anthropic import RateLimitError
        except ImportError:
            RateLimitError = Exception

        model_to_use = self.model_name
        try:
            async with self.client.messages.stream(
                model=model_to_use,
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                async for text in stream.text_stream:
                    yield text

        except RateLimitError as e:
            logger.warning(f"RateLimitError on {self.model_name} during streaming: {e}")
            if self.no_fallback:
                async for text in self._retry_stream_with_backoff(prompt):
                    yield text
                return
            if model_to_use == self.model_name:
                logger.warning(f"Falling back to {self.fallback_model}")
                try:
                    async with self.client.messages.stream(
                        model=self.fallback_model,
                        max_tokens=8192,
                        messages=[{"role": "user", "content": prompt}],
                    ) as stream:
                        logger.info(f"Successfully started streaming with fallback model {self.fallback_model}")
                        async for text in stream.text_stream:
                            yield text
                except Exception as fallback_error:
                    raise RuntimeError(
                        f"Error in streaming generation (fallback model {self.fallback_model}): {fallback_error}"
                    )
            else:
                raise RuntimeError(f"Rate limit error in streaming generation: {model_to_use}")
        except Exception as e:
            raise RuntimeError(f"Error in streaming generation: {e}")

    async def _retry_with_backoff(self, prompt: str) -> str:
        """Retry the same model with exponential backoff on rate limit errors."""
        try:
            from anthropic import RateLimitError
        except ImportError:
            RateLimitError = Exception

        for attempt, delay in enumerate(RETRY_DELAYS, 1):
            logger.warning(f"Rate limit (429) on {self.model_name}, retry {attempt}/{len(RETRY_DELAYS)} in {delay}s")
            await asyncio.sleep(delay)
            try:
                response = await self.client.messages.create(
                    model=self.model_name,
                    max_tokens=8192,
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.content[0].text.strip()
            except RateLimitError:
                continue
            except Exception as retry_error:
                raise RuntimeError(f"Error calling Anthropic: {retry_error}")
        raise RuntimeError(f"Rate limit on {self.model_name} after {len(RETRY_DELAYS)} retries")

    async def _retry_stream_with_backoff(self, prompt: str) -> AsyncGenerator[str, None]:
        """Retry streaming with the same model using exponential backoff."""
        try:
            from anthropic import RateLimitError
        except ImportError:
            RateLimitError = Exception

        for attempt, delay in enumerate(RETRY_DELAYS, 1):
            logger.warning(
                f"Rate limit (429) on {self.model_name} during streaming, "
                f"retry {attempt}/{len(RETRY_DELAYS)} in {delay}s"
            )
            await asyncio.sleep(delay)
            try:
                async with self.client.messages.stream(
                    model=self.model_name,
                    max_tokens=8192,
                    messages=[{"role": "user", "content": prompt}],
                ) as stream:
                    async for text in stream.text_stream:
                        yield text
                return
            except RateLimitError:
                continue
            except Exception as retry_error:
                raise RuntimeError(f"Error in streaming generation: {retry_error}")
        raise RuntimeError(f"Rate limit on {self.model_name} after {len(RETRY_DELAYS)} retries")

    def get_model_name(self) -> str:
        """Return the primary model name."""
        return self.model_name

    def get_provider_name(self) -> str:
        """Return the provider name."""
        return "anthropic"
