"""In-process pub/sub for wire events.

Every state mutation in ``core`` publishes a :data:`skene.schema.Event`
here; the SSE route and the CLI's embedded progress renderer subscribe.
Events are scoped to a workspace ``directory`` so one server can host
many projects (opencode's directory filtering): a subscriber with a
directory filter receives that directory's events plus server-wide ones
(published with ``directory=None``, e.g. heartbeats).

Subscriber queues are unbounded — sessions produce events at LLM speed,
so a slow consumer buffers a handful of small models, not a firehose.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from skene.schema import Event


def normalize_directory(directory: str | Path) -> str:
    """Canonical form used for directory equality across the server."""
    return str(Path(directory).expanduser().resolve())


class Subscription:
    """One subscriber's view of the bus. Async-iterate to consume."""

    def __init__(self, bus: Bus, directory: str | None) -> None:
        self._bus = bus
        self.directory = directory
        self._queue: asyncio.Queue[Event | None] = asyncio.Queue()

    def _offer(self, event: Event, directory: str | None) -> None:
        if self.directory is None or directory is None or directory == self.directory:
            self._queue.put_nowait(event)

    async def get(self, timeout: float | None = None) -> Event | None:
        """Next event, or ``None`` on timeout (used for SSE heartbeats)."""
        if timeout is None:
            return await self._queue.get()
        try:
            return await asyncio.wait_for(self._queue.get(), timeout)
        except TimeoutError:
            return None

    def __aiter__(self) -> Subscription:
        return self

    async def __anext__(self) -> Event:
        event = await self._queue.get()
        if event is None:
            raise StopAsyncIteration
        return event

    def close(self) -> None:
        self._bus._unsubscribe(self)
        self._queue.put_nowait(None)  # unblock a pending get()


class Bus:
    def __init__(self) -> None:
        self._subscriptions: set[Subscription] = set()

    def subscribe(self, directory: str | Path | None = None) -> Subscription:
        sub = Subscription(self, normalize_directory(directory) if directory is not None else None)
        self._subscriptions.add(sub)
        return sub

    def _unsubscribe(self, sub: Subscription) -> None:
        self._subscriptions.discard(sub)

    def publish(self, event: Event, *, directory: str | Path | None = None) -> None:
        """Fan an event out to matching subscribers. Never blocks."""
        resolved = normalize_directory(directory) if directory is not None else None
        for sub in list(self._subscriptions):
            sub._offer(event, resolved)
