"""
Base class for OpenAI-compatible LLM providers.

This module provides a common implementation for providers that use
the OpenAI API protocol (OpenAI, LM Studio, Ollama, and generic endpoints).
"""

from typing import AsyncGenerator, Optional

from pydantic import SecretStr

from skene.llm.base import LLMClient

DEFAULT_TIMEOUT = 900.0


class OpenAICompatibleClient(LLMClient):
    """
    Base class for OpenAI-compatible LLM clients.

    Provides common implementation for providers that use the OpenAI API protocol.
    Subclasses should set provider-specific defaults and override get_provider_name().

    Example:
        class MyClient(OpenAICompatibleClient):
            def get_provider_name(self) -> str:
                return "my-provider"
    """

    def __init__(
        self,
        api_key: SecretStr,
        model_name: str,
        base_url: Optional[str] = None,
        default_api_key: str = "not-required",
    ):
        """
        Initialize the OpenAI-compatible client.

        Args:
            api_key: API key for the service (wrapped in SecretStr for security)
            model_name: Model name to use
            base_url: Base URL for the API endpoint. If None, uses OpenAI's default.
            default_api_key: Default API key to use if none provided (for local services)
        """
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError(
                "openai is required for OpenAI-compatible providers. Install with: pip install skene[openai]"
            )

        self.model_name = model_name
        self.base_url = base_url

        # Use provided API key or fall back to default
        api_key_value = api_key.get_secret_value() if api_key else default_api_key

        # Build client kwargs
        client_kwargs = {"api_key": api_key_value}
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = AsyncOpenAI(timeout=DEFAULT_TIMEOUT, **client_kwargs)

    async def generate_content(
        self,
        prompt: str,
    ) -> str:
        """
        Generate text from the LLM.

        Args:
            prompt: The prompt to send to the model

        Returns:
            Generated text as a string

        Raises:
            RuntimeError: If generation fails
        """
        content, _ = await self.generate_content_with_usage(prompt)
        return content

    async def generate_content_with_usage(
        self,
        prompt: str,
    ) -> tuple[str, dict[str, int] | None]:
        """Generate text and return (content, usage). Usage has output_tokens, input_tokens. Returns None when not in response."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.choices[0].message.content.strip()
            usage = getattr(response, "usage", None)
            if usage and hasattr(usage, "prompt_tokens") and hasattr(usage, "completion_tokens"):
                return (content, {"output_tokens": usage.completion_tokens, "input_tokens": usage.prompt_tokens})
            return (content, None)
        except Exception as e:
            raise RuntimeError(f"Error calling {self.get_provider_name()}: {e}")

    async def generate_content_stream(
        self,
        prompt: str,
    ) -> AsyncGenerator[str, None]:
        """
        Generate content with streaming.

        Args:
            prompt: The prompt to send to the model

        Yields:
            Text chunks as they are generated

        Raises:
            RuntimeError: If streaming fails
        """
        try:
            stream = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            raise RuntimeError(f"Error in {self.get_provider_name()} streaming generation: {e}")

    def get_model_name(self) -> str:
        """Return the model name."""
        return self.model_name

    def get_provider_name(self) -> str:
        """Return the provider name. Subclasses should override this."""
        return "openai-compatible"
