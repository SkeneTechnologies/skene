"""FastAPI application factory.

Two construction modes:

- ``create_app()`` — the ``skene serve`` path: services are built inside
  the lifespan (so the store opens on uvicorn's event loop) and torn down
  on shutdown.
- ``create_app(services=...)`` — tests and embedded callers pass prebuilt
  services and own their lifecycle; the lifespan does nothing.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI
from pydantic import TypeAdapter

from skene import __version__
from skene.core.services import CoreServices, create_services
from skene.core.sessions import LLMFactory
from skene.schema import Event, ServerConfigInfo
from skene.server.deps import require_auth
from skene.server.routes import agent, config, event, journey, session


def create_app(
    services: CoreServices | None = None,
    *,
    db_path: Path | str | None = None,
    llm_factory: LLMFactory | None = None,
    auth_token: str | None = None,
    config_info: ServerConfigInfo | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        owned = services is None
        app.state.services = (
            services if services is not None else await create_services(db_path, llm_factory, config_info=config_info)
        )
        try:
            yield
        finally:
            if owned:
                await app.state.services.close()

    app = FastAPI(
        title="skene",
        version=__version__,
        description="Backend server for the skene analysis engine.",
        lifespan=lifespan,
    )
    app.state.auth_token = auth_token
    if services is not None:
        # Available before startup too, so in-process tests can skip the lifespan.
        app.state.services = services

    protected = [Depends(require_auth)]
    app.include_router(session.router, dependencies=protected)
    app.include_router(event.router, dependencies=protected)
    app.include_router(journey.router, dependencies=protected)
    app.include_router(agent.router, dependencies=protected)
    app.include_router(config.router, dependencies=protected)

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/doc", tags=["meta"], include_in_schema=False)
    async def doc() -> dict[str, Any]:
        """The OpenAPI document (alias of ``/openapi.json``, per the design)."""
        return app.openapi()

    _default_openapi = app.openapi

    def openapi_with_events() -> dict[str, Any]:
        """Inject the SSE ``Event`` union into the spec.

        ``GET /event`` streams, so FastAPI can't derive a response model for
        it — but generated clients (the Go TUI) still need the event types.
        The union goes in as ``components.schemas.Event`` and as the
        ``text/event-stream`` content schema of the route; definitions
        FastAPI already emitted for the REST routes are left untouched.
        """
        if app.openapi_schema:
            return app.openapi_schema
        spec = _default_openapi()
        event_schema = TypeAdapter(Event).json_schema(ref_template="#/components/schemas/{model}")
        schemas = spec.setdefault("components", {}).setdefault("schemas", {})
        for name, definition in event_schema.pop("$defs", {}).items():
            schemas.setdefault(name, definition)
        schemas["Event"] = event_schema
        spec["paths"]["/event"]["get"]["responses"]["200"]["content"] = {
            "text/event-stream": {"schema": {"$ref": "#/components/schemas/Event"}}
        }
        app.openapi_schema = spec
        return spec

    app.openapi = openapi_with_events  # type: ignore[method-assign]

    return app
