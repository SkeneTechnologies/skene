"""
Ollama LLM client implementation.

EXPERIMENTAL: This provider has not been fully tested. Please report any issues.

Ollama provides an OpenAI-compatible API for running local LLMs.
Default endpoint: http://localhost:11434/v1
"""

import os
from typing import Optional

from loguru import logger
from pydantic import SecretStr

from skene.llm.providers.openai_compat import OpenAICompatibleClient

# Default Ollama server URL
DEFAULT_BASE_URL = "http://localhost:11434/v1"


class OllamaClient(OpenAICompatibleClient):
    """
    Ollama LLM client.

    EXPERIMENTAL: This provider has not been fully tested.

    Uses the OpenAI-compatible API provided by Ollama for local LLM inference.
    The base URL can be configured via the OLLAMA_BASE_URL environment variable
    or passed directly to the constructor.

    Example:
        client = OllamaClient(
            api_key=SecretStr("ollama"),  # API key is optional for local use
            model_name="llama3.3"
        )
        response = await client.generate_content("Hello!")
    """

    def __init__(
        self,
        api_key: SecretStr,
        model_name: str,
        base_url: Optional[str] = None,
    ):
        """
        Initialize the Ollama client.

        Args:
            api_key: API key (can be any value for local Ollama)
            model_name: Model name available in Ollama
            base_url: Ollama server URL (default: http://localhost:11434/v1)
                      Can also be set via OLLAMA_BASE_URL environment variable
        """
        resolved_base_url = base_url or os.environ.get("OLLAMA_BASE_URL", DEFAULT_BASE_URL)

        super().__init__(
            api_key=api_key,
            model_name=model_name,
            base_url=resolved_base_url,
            default_api_key="ollama",
        )

        logger.debug(f"Ollama client initialized with base_url: {self.base_url}")

    def get_provider_name(self) -> str:
        """Return the provider name."""
        return "ollama"
