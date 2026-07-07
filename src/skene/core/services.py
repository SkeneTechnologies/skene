"""Wiring for the core services (store + bus + sessions + agent registry).

Both entry points build this the same way: the HTTP server constructs it
in its lifespan, the embedded CLI constructs it directly and calls core
functions without a socket.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from skene.core.agents import AgentRegistry
from skene.core.bus import Bus
from skene.core.journey import make_run_factory
from skene.core.permissions import PermissionService
from skene.core.sessions import LLMFactory, SessionService
from skene.core.store import DEFAULT_DB_PATH, Store
from skene.schema import ServerConfigInfo


def resolve_db_path(db_path: Path | str | None = None) -> Path:
    """Explicit argument > ``SKENE_DB_PATH`` env > the global default."""
    if db_path is not None:
        return Path(db_path).expanduser()
    env = os.environ.get("SKENE_DB_PATH")
    if env:
        return Path(env).expanduser()
    return DEFAULT_DB_PATH


def _no_llm_configured() -> "LLMFactory":
    def factory():  # type: ignore[return-value]
        raise RuntimeError(
            "no LLM configured for this server — set provider credentials in .skene.config or SKENE_API_KEY"
        )

    return factory


@dataclass
class CoreServices:
    store: Store
    bus: Bus
    sessions: SessionService
    registry: AgentRegistry
    permissions: PermissionService
    # Startup-resolved LLM config snapshot for GET /config and GET /provider;
    # None for bare service setups (tests, embedded CLI).
    config_info: ServerConfigInfo | None = None

    async def close(self) -> None:
        await self.store.close()


async def create_services(
    db_path: Path | str | None = None,
    llm_factory: LLMFactory | None = None,
    registry: AgentRegistry | None = None,
    config_info: ServerConfigInfo | None = None,
) -> CoreServices:
    store = await Store.open(resolve_db_path(db_path))
    bus = Bus()
    registry = registry or AgentRegistry()
    permissions = PermissionService(store, bus)
    sessions = SessionService(store, bus, llm_factory or _no_llm_configured())
    sessions.run_factory = make_run_factory(sessions, registry, permissions)
    return CoreServices(
        store=store,
        bus=bus,
        sessions=sessions,
        registry=registry,
        permissions=permissions,
        config_info=config_info,
    )
