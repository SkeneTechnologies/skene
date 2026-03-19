"""
LLM client factory.
"""

from typing import Optional

from pydantic import SecretStr

from skene.llm.base import LLMClient


def create_llm_client(
    provider: str,
    api_key: SecretStr,
    model_name: str,
    base_url: Optional[str] = None,
    debug: bool = False,
    no_fallback: Optional[bool] = False,
) -> LLMClient:
    """
    Factory function to create an LLM client based on provider.

    Args:
        provider: Provider name (e.g., "gemini", "openai", "generic")
        api_key: API key wrapped in SecretStr for security
        model_name: Model name to use
        base_url: Optional base URL for the API endpoint (required for "generic" provider)
        debug: When True, wrap the client with DebugLLMClient to log all LLM I/O
        no_fallback: When True, disable model fallback on 429 errors and retry same model instead

    Returns:
        Instance of LLMClient implementation

    Raises:
        ValueError: If provider is not supported or required parameters are missing
        NotImplementedError: If provider is known but not yet implemented

    Example:
        # Using a known provider
        client = create_llm_client(
            provider="gemini",
            api_key=SecretStr("your-api-key"),
            model_name="gemini-3-flash-preview"
        )

        # Using a generic OpenAI-compatible endpoint
        client = create_llm_client(
            provider="generic",
            api_key=SecretStr("your-api-key"),
            model_name="your-model",
            base_url="https://your-service.com/v1"
        )
    """
    match provider.lower():
        case "gemini":
            from skene.llm.providers.gemini import GoogleGeminiClient

            client = GoogleGeminiClient(api_key=api_key, model_name=model_name, no_fallback=no_fallback)
        case "openai":
            from skene.llm.providers.openai import OpenAIClient

            client = OpenAIClient(api_key=api_key, model_name=model_name, no_fallback=no_fallback)
        case "anthropic" | "claude":
            from skene.llm.providers.anthropic import AnthropicClient

            client = AnthropicClient(api_key=api_key, model_name=model_name, no_fallback=no_fallback)
        case "lmstudio" | "lm-studio" | "lm_studio":
            from skene.llm.providers.lmstudio import LMStudioClient

            client = LMStudioClient(api_key=api_key, model_name=model_name, base_url=base_url)
        case "ollama":
            from skene.llm.providers.ollama import OllamaClient

            client = OllamaClient(api_key=api_key, model_name=model_name, base_url=base_url)
        case "generic" | "openai-compatible" | "openai_compatible":
            from skene.llm.providers.generic import GenericClient

            if not base_url:
                raise ValueError("base_url is required for the generic provider")
            client = GenericClient(api_key=api_key, model_name=model_name, base_url=base_url)
        case "skene":
            from skene.llm.providers.skene import SkeneClient

            client = SkeneClient(api_key=api_key, model_name=model_name, base_url=base_url)
        case _:
            raise ValueError(f"Unknown provider: {provider}")

    if debug:
        from skene.llm.debug import DebugLLMClient

        client = DebugLLMClient(client)

    return client
