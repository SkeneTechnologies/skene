"""
Generic OpenAI-compatible LLM client implementation.

Allows users to connect to any OpenAI-compatible API endpoint
by specifying a custom base URL and API key.
"""

from typing import Optional

from loguru import logger
from pydantic import SecretStr

from skene.llm.providers.openai_compat import OpenAICompatibleClient


class GenericClient(OpenAICompatibleClient):
    """
    Generic OpenAI-compatible LLM client.

    Allows connecting to any service that implements the OpenAI API protocol.
    Requires a base_url to be specified.

    Example:
        client = GenericClient(
            api_key=SecretStr("your-api-key"),
            model_name="your-model",
            base_url="https://your-service.com/v1"
        )
        response = await client.generate_content("Hello!")
    """

    def __init__(
        self,
        api_key: SecretStr,
        model_name: str,
        base_url: str,
        provider_name: Optional[str] = None,
    ):
        """
        Initialize the generic OpenAI-compatible client.

        Args:
            api_key: API key for the service (wrapped in SecretStr for security)
            model_name: Model name to use
            base_url: Base URL for the API endpoint (required)
            provider_name: Optional custom provider name for logging/identification
        """
        if not base_url:
            raise ValueError("base_url is required for the generic provider")

        super().__init__(
            api_key=api_key,
            model_name=model_name,
            base_url=base_url,
            default_api_key="not-required",
        )

        self._provider_name = provider_name or "generic"

        logger.debug(f"Generic client initialized with base_url: {self.base_url}")

    def get_provider_name(self) -> str:
        """Return the provider name."""
        return self._provider_name
