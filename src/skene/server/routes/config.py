"""The config / provider surface, read-only (phase 5).

The server resolves its LLM configuration once at startup, so ``GET
/config`` reports that snapshot and there is no PATCH: changing provider
or credentials means restarting ``skene serve`` (a deliberate choice —
rebuilding the LLM factory mid-flight buys nothing while runs are in
progress). Secrets are redacted to a boolean.
"""

from __future__ import annotations

from fastapi import APIRouter

from skene import __version__
from skene.config import DEFAULT_MODEL_BY_PROVIDER
from skene.schema import ProviderInfo, ServerConfigInfo
from skene.server.deps import Services

router = APIRouter(tags=["config"])

# The canonical provider names understood by skene.llm.factory (aliases
# like "claude" or "lm-studio" are accepted on input but not listed).
_SUPPORTED_PROVIDERS = ("skene", "anthropic", "openai", "gemini", "lmstudio", "ollama", "generic")


@router.get("/config", response_model=ServerConfigInfo)
async def get_config(services: Services) -> ServerConfigInfo:
    """The server's resolved LLM configuration, secrets redacted."""
    info = services.config_info
    if info is None:
        return ServerConfigInfo(version=__version__)
    return info.model_copy(update={"version": __version__})


@router.get("/provider", response_model=list[ProviderInfo])
async def list_providers(services: Services) -> list[ProviderInfo]:
    """Supported LLM providers; ``active`` marks the one the server runs with."""
    active = services.config_info.provider.lower() if services.config_info and services.config_info.provider else None
    providers = []
    for name in _SUPPORTED_PROVIDERS:
        default_model = DEFAULT_MODEL_BY_PROVIDER.get(name)
        providers.append(
            ProviderInfo(
                name=name,
                models=[default_model] if default_model else [],
                active=name == active,
            )
        )
    return providers
