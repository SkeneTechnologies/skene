"""Tests for the /event SSE stream."""

from __future__ import annotations

import asyncio
import json

from skene.core.bus import Bus
from skene.schema import ServerHeartbeat
from skene.server.sse import event_stream
from tests.fakes import ScriptedClient, turn


def _parse(frame: str) -> dict:
    assert frame.startswith("data: ") and frame.endswith("\n\n")
    return json.loads(frame[len("data: ") :])


async def test_stream_opens_with_connected_then_delivers_events():
    bus = Bus()
    stream = event_stream(bus, directory=None)
    connected = _parse(await anext(stream))
    assert connected["type"] == "server.connected"
    assert connected["id"].startswith("evt_")

    bus.publish(ServerHeartbeat())
    event = _parse(await asyncio.wait_for(anext(stream), timeout=1))
    assert event["type"] == "server.heartbeat"
    await stream.aclose()


async def test_stream_emits_heartbeat_on_idle():
    bus = Bus()
    stream = event_stream(bus, directory=None, heartbeat_seconds=0.05)
    await anext(stream)  # server.connected
    event = _parse(await asyncio.wait_for(anext(stream), timeout=1))
    assert event["type"] == "server.heartbeat"
    await stream.aclose()


async def test_stream_filters_by_directory(tmp_path):
    mine = tmp_path / "mine"
    mine.mkdir()
    other = tmp_path / "other"
    other.mkdir()

    bus = Bus()
    stream = event_stream(bus, directory=str(mine), heartbeat_seconds=0.05)
    await anext(stream)  # server.connected

    scoped = ServerHeartbeat()
    bus.publish(scoped, directory=str(other))
    # The other workspace's event must not arrive — next frame is an idle heartbeat.
    event = _parse(await asyncio.wait_for(anext(stream), timeout=1))
    assert event["id"] != scoped.id
    await stream.aclose()


async def test_http_event_route_streams(app, client, services, workspace):
    """Full loop: prompt a session and watch its events arrive over HTTP SSE.

    httpx's ASGITransport buffers whole responses, which deadlocks on an
    endless SSE body — so this test speaks raw ASGI to the app for the
    stream and uses the normal client for the mutating calls.
    """
    services.sessions.llm_factory = lambda: ScriptedClient([turn(text="hi")])

    types: list[str] = []
    headers_seen: dict[bytes, bytes] = {}
    saw_idle = asyncio.Event()

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/event",
        "raw_path": b"/event",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"x-skene-directory", str(workspace).encode())],
        "client": ("test", 123),
        "server": ("skene.test", 80),
    }

    async def receive():
        # Simulate the client hanging up once we've seen the run finish.
        await saw_idle.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.start":
            headers_seen.update(dict(message["headers"]))
        elif message["type"] == "http.response.body":
            for line in message.get("body", b"").decode().splitlines():
                if not line.startswith("data: "):
                    continue
                event = json.loads(line[len("data: ") :])
                types.append(event["type"])
                if event["type"] == "session.idle":
                    saw_idle.set()

    stream_task = asyncio.create_task(app(scope, receive, send))
    while "server.connected" not in types:  # wait for the subscription to exist
        await asyncio.sleep(0.01)

    session_id = (await client.post("/session", json={})).json()["id"]
    await client.post(f"/session/{session_id}/message", json={"text": "hello"})
    await asyncio.wait_for(stream_task, timeout=5)

    assert headers_seen[b"content-type"].startswith(b"text/event-stream")
    assert types[0] == "server.connected"
    assert "session.created" in types
    assert "message.created" in types
    assert "part.created" in types
    assert types[-1] == "session.idle"


async def test_event_route_rejects_bad_auth(services, workspace):
    import httpx

    from skene.server import create_app

    app = create_app(services, auth_token="sekrit")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://skene.test") as client:
        assert (await client.get("/event")).status_code == 401
