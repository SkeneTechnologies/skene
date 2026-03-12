"""
Abstract base class for LLM clients.
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator


class LLMClient(ABC):
    """
    Abstract base class for LLM clients.

    Provides a unified interface to interact with different LLM providers.
    Implementations should handle provider-specific details internally.

    Example:
        client = create_llm_client("gemini", api_key, "gemini-3-flash-preview")
        response = await client.generate_content("Hello, world!")
    """

    @abstractmethod
    async def generate_content(
        self,
        prompt: str,
    ) -> str:
        """
        Generate text from the LLM.

        Args:
            prompt: User input or message content

        Returns:
            Generated text as a string
        """
        pass

    @abstractmethod
    async def generate_content_stream(
        self,
        prompt: str,
    ) -> AsyncGenerator[str, None]:
        """
        Generate text from the LLM with streaming.

        Args:
            prompt: User input or message content

        Yields:
            Text chunks as they are generated
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the name of the underlying model."""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the provider name (e.g., 'google', 'openai')."""
        pass

    async def generate_content_with_usage(
        self, prompt: str
    ) -> tuple[str, dict[str, int] | None]:
        """Generate content and return (content, usage). Usage dict has output_tokens, input_tokens. Returns None when not available."""
        content = await self.generate_content(prompt)
        return (content, None)
