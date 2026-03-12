"""
LM Studio LLM client implementation.

LM Studio provides an OpenAI-compatible API for running local LLMs.
Default endpoint: http://localhost:1234/v1
"""

import os
from typing import Optional

from loguru import logger
from pydantic import SecretStr

from skene.llm.providers.openai_compat import OpenAICompatibleClient

# Default LM Studio server URL
DEFAULT_BASE_URL = "http://localhost:1234/v1"


class LMStudioClient(OpenAICompatibleClient):
    """
    LM Studio LLM client.

    Uses the OpenAI-compatible API provided by LM Studio for local LLM inference.
    The base URL can be configured via the LMSTUDIO_BASE_URL environment variable
    or passed directly to the constructor.

    Example:
        client = LMStudioClient(
            api_key=SecretStr("lm-studio"),  # API key is optional for local use
            model_name="local-model"
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
        Initialize the LM Studio client.

        Args:
            api_key: API key (can be any value for local LM Studio)
            model_name: Model name loaded in LM Studio
            base_url: LM Studio server URL (default: http://localhost:1234/v1)
                      Can also be set via LMSTUDIO_BASE_URL environment variable
        """
        resolved_base_url = base_url or os.environ.get("LMSTUDIO_BASE_URL", DEFAULT_BASE_URL)

        super().__init__(
            api_key=api_key,
            model_name=model_name,
            base_url=resolved_base_url,
            default_api_key="lm-studio",
        )

        logger.debug(f"LM Studio client initialized with base_url: {self.base_url}")

    def get_provider_name(self) -> str:
        """Return the provider name."""
        return "lmstudio"
