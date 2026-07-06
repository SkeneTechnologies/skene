"""Wiring for the core services (store + bus + session service).

Both entry points build this the same way: the HTTP server constructs it
in its lifespan, the embedded CLI constructs it directly and calls core
functions without a socket.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from skene.core.bus import Bus
from skene.core.sessions import LLMFactory, SessionService
from skene.core.store import DEFAULT_DB_PATH, Store


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

    async def close(self) -> None:
        await self.store.close()


async def create_services(
    db_path: Path | str | None = None,
    llm_factory: LLMFactory | None = None,
) -> CoreServices:
    store = await Store.open(resolve_db_path(db_path))
    bus = Bus()
    sessions = SessionService(store, bus, llm_factory or _no_llm_configured())
    return CoreServices(store=store, bus=bus, sessions=sessions)
