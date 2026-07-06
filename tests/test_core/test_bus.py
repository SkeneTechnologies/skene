"""Tests for the in-process event bus."""

from __future__ import annotations

import asyncio

from skene.core.bus import Bus, normalize_directory
from skene.schema import ServerHeartbeat


async def test_publish_reaches_subscriber():
    bus = Bus()
    sub = bus.subscribe()
    event = ServerHeartbeat()
    bus.publish(event)
    assert await sub.get(timeout=1) is event


async def test_directory_filtering():
    bus = Bus()
    watcher_a = bus.subscribe("/tmp/a")
    watcher_all = bus.subscribe()

    scoped = ServerHeartbeat()
    bus.publish(scoped, directory="/tmp/b")
    # The /tmp/a watcher must not see /tmp/b's event; the unfiltered one must.
    assert await watcher_all.get(timeout=1) is scoped
    assert await watcher_a.get(timeout=0.05) is None

    matching = ServerHeartbeat()
    bus.publish(matching, directory="/tmp/a")
    assert await watcher_a.get(timeout=1) is matching

    server_wide = ServerHeartbeat()
    bus.publish(server_wide)  # no directory → everyone
    assert await watcher_a.get(timeout=1) is server_wide
    assert await watcher_all.get(timeout=1) is matching  # queued earlier


async def test_directory_comparison_is_normalized(tmp_path):
    bus = Bus()
    sub = bus.subscribe(tmp_path)
    event = ServerHeartbeat()
    # Publish with a non-canonical spelling of the same directory.
    bus.publish(event, directory=str(tmp_path) + "/.")
    assert await sub.get(timeout=1) is event
    assert sub.directory == normalize_directory(tmp_path)


async def test_close_stops_iteration():
    bus = Bus()
    sub = bus.subscribe()

    async def consume():
        return [e async for e in sub]

    task = asyncio.create_task(consume())
    await asyncio.sleep(0)
    event = ServerHeartbeat()
    bus.publish(event)
    sub.close()
    assert await asyncio.wait_for(task, timeout=1) == [event]
    # After close, publishes don't reach the subscription.
    bus.publish(ServerHeartbeat())
    assert sub._queue.qsize() == 0
