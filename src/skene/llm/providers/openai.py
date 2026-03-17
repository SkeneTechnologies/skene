"""
OpenAI LLM client implementation.
"""

import asyncio
from typing import AsyncGenerator, Optional

from loguru import logger
from pydantic import SecretStr

from skene.llm.providers.openai_compat import OpenAICompatibleClient

# Default fallback model for rate limiting (429 errors)
DEFAULT_FALLBACK_MODEL = "gpt-4o-mini"

# Retry delays in seconds for no-fallback mode (exponential-ish backoff)
RETRY_DELAYS = [5, 15, 30]


class OpenAIClient(OpenAICompatibleClient):
    """
    OpenAI LLM client.

    Handles rate limiting by automatically falling back to a secondary model
    when the primary model returns a 429 rate limit error.

    Example:
        client = OpenAIClient(
            api_key=SecretStr("your-api-key"),
            model_name="gpt-4o"
        )
        response = await client.generate_content("Hello!")
    """

    def __init__(
        self,
        api_key: SecretStr,
        model_name: str,
        fallback_model: Optional[str] = None,
        no_fallback: bool = False,
    ):
        """
        Initialize the OpenAI client.

        Args:
            api_key: OpenAI API key (wrapped in SecretStr for security)
            model_name: Primary model to use (e.g., "gpt-4o", "gpt-4o-mini")
            fallback_model: Model to use when rate limited (default: gpt-4o-mini)
            no_fallback: When True, retry same model on 429 instead of falling back
        """
        super().__init__(api_key=api_key, model_name=model_name)
        self.fallback_model = fallback_model or DEFAULT_FALLBACK_MODEL
        self.no_fallback = no_fallback

    def _usage_from_response(self, response) -> dict[str, int] | None:
        usage = getattr(response, "usage", None)
        if usage and hasattr(usage, "prompt_tokens") and hasattr(usage, "completion_tokens"):
            return {"output_tokens": usage.completion_tokens, "input_tokens": usage.prompt_tokens}
        return None

    async def generate_content_with_usage(
        self,
        prompt: str,
    ) -> tuple[str, dict[str, int] | None]:
        """Generate text and return (content, usage). Honors fallback/retry on rate limit."""
        try:
            from openai import RateLimitError
        except ImportError:
            RateLimitError = Exception
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.choices[0].message.content.strip()
            return (content, self._usage_from_response(response))
        except RateLimitError as e:
            logger.warning(f"RateLimitError on {self.model_name}: {e}")
            if self.no_fallback:
                content = await self._retry_with_backoff(prompt)
                return (content, None)
            logger.warning(f"Falling back to {self.fallback_model}")
            try:
                response = await self.client.chat.completions.create(
                    model=self.fallback_model,
                    messages=[{"role": "user", "content": prompt}],
                )
                logger.info(f"Successfully generated content using fallback model {self.fallback_model}")
                content = response.choices[0].message.content.strip()
                return (content, self._usage_from_response(response))
            except Exception as fallback_error:
                raise RuntimeError(f"Error calling OpenAI (fallback model {self.fallback_model}): {fallback_error}")
        except Exception as e:
            raise RuntimeError(f"Error calling OpenAI: {e}")

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
            from openai import RateLimitError
        except ImportError:
            RateLimitError = Exception

        model_to_use = self.model_name
        try:
            stream = await self.client.chat.completions.create(
                model=model_to_use,
                messages=[{"role": "user", "content": prompt}],
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except RateLimitError as e:
            logger.warning(f"RateLimitError on {self.model_name} during streaming: {e}")
            if self.no_fallback:
                async for chunk in self._retry_stream_with_backoff(prompt):
                    yield chunk
                return
            if model_to_use == self.model_name:
                logger.warning(f"Falling back to {self.fallback_model}")
                try:
                    stream = await self.client.chat.completions.create(
                        model=self.fallback_model,
                        messages=[{"role": "user", "content": prompt}],
                        stream=True,
                    )
                    logger.info(f"Successfully started streaming with fallback model {self.fallback_model}")
                    async for chunk in stream:
                        if chunk.choices and chunk.choices[0].delta.content:
                            yield chunk.choices[0].delta.content
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
            from openai import RateLimitError
        except ImportError:
            RateLimitError = Exception

        for attempt, delay in enumerate(RETRY_DELAYS, 1):
            logger.warning(f"Rate limit (429) on {self.model_name}, retry {attempt}/{len(RETRY_DELAYS)} in {delay}s")
            await asyncio.sleep(delay)
            try:
                response = await self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.choices[0].message.content.strip()
            except RateLimitError:
                continue
            except Exception as retry_error:
                raise RuntimeError(f"Error calling OpenAI: {retry_error}")
        raise RuntimeError(f"Rate limit on {self.model_name} after {len(RETRY_DELAYS)} retries")

    async def _retry_stream_with_backoff(self, prompt: str) -> AsyncGenerator[str, None]:
        """Retry streaming with the same model using exponential backoff."""
        try:
            from openai import RateLimitError
        except ImportError:
            RateLimitError = Exception

        for attempt, delay in enumerate(RETRY_DELAYS, 1):
            logger.warning(
                f"Rate limit (429) on {self.model_name} during streaming, "
                f"retry {attempt}/{len(RETRY_DELAYS)} in {delay}s"
            )
            await asyncio.sleep(delay)
            try:
                stream = await self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    stream=True,
                )
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                return
            except RateLimitError:
                continue
            except Exception as retry_error:
                raise RuntimeError(f"Error in streaming generation: {retry_error}")
        raise RuntimeError(f"Rate limit on {self.model_name} after {len(RETRY_DELAYS)} retries")

    def get_provider_name(self) -> str:
        """Return the provider name."""
        return "openai"
