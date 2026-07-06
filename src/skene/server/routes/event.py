"""The ``GET /event`` SSE stream."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse

from skene.server.deps import Services
from skene.server.sse import event_stream

router = APIRouter(tags=["event"])


@router.get("/event")
async def events(
    services: Services,
    x_skene_directory: Annotated[str | None, Header()] = None,
) -> StreamingResponse:
    """Stream every bus event as SSE.

    With an ``x-skene-directory`` header, only that workspace's events (plus
    server-wide ones like heartbeats) are delivered; without it the stream
    is unfiltered — unlike the REST routes, which fall back to the server
    cwd, a global observer is the more useful default for an event tap.
    """
    return StreamingResponse(
        event_stream(services.bus, x_skene_directory),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
