"""Server-sent-events encoding for the ``/event`` stream."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from skene.core.bus import Bus
from skene.schema import Event, ServerConnected, ServerHeartbeat

HEARTBEAT_SECONDS = 10.0


def encode(event: Event) -> str:
    """One SSE frame: the event's wire JSON in a ``data:`` line."""
    return f"data: {event.model_dump_json()}\n\n"


async def event_stream(
    bus: Bus,
    directory: str | None,
    heartbeat_seconds: float = HEARTBEAT_SECONDS,
) -> AsyncGenerator[str, None]:
    """Subscribe to the bus and yield SSE frames until the client goes away.

    Opens with ``server.connected`` and emits ``server.heartbeat`` after
    every ``heartbeat_seconds`` of silence so proxies keep the connection
    alive (opencode's semantics).
    """
    subscription = bus.subscribe(directory)
    try:
        yield encode(ServerConnected())
        while True:
            event = await subscription.get(timeout=heartbeat_seconds)
            yield encode(event if event is not None else ServerHeartbeat())
    finally:
        subscription.close()
