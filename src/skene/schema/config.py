"""Config / provider surface wire models (phase 5).

``GET /config`` is deliberately read-only: the server resolves its LLM
config once at startup (flags/env/.skene.config), so changing it means
restarting the server — a PATCH that rebuilt the factory mid-flight was
considered and rejected for now. Secrets never appear here: the API key
is reported only as a boolean.
"""

from __future__ import annotations

from pydantic import Field

from skene.schema.base import WireModel


class ProviderInfo(WireModel):
    """One supported LLM provider, as exposed by ``GET /provider``."""

    name: str
    models: list[str] = Field(default_factory=list)
    # True for the provider the server was started with.
    active: bool = False


class ServerConfigInfo(WireModel):
    """Resolved server configuration, secrets redacted (``GET /config``)."""

    version: str
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    api_key_configured: bool = False
