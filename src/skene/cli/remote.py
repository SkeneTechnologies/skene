"""HTTP client for driving a remote skene server (``skene attach``).

The embedded path (:mod:`skene.core.embedded`) calls core services
in-process; this module is its remote twin — the same canned journey run
driven over HTTP + SSE against a server started elsewhere. Kept
deliberately small: one health probe and one journey runner. Progress
rendering folds the event stream into the same ``status()`` lines the
embedded run prints.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from skene.output import status, warning
from skene.schema import JourneyAnalyseRequest

DIRECTORY_HEADER = "x-skene-directory"

# One frame larger than this indicates a broken stream (mirrors the TUI cap).
_MAX_EVENT_SIZE = 16 * 1024 * 1024


class RemoteServerError(RuntimeError):
    """The remote server is unreachable, unauthorized, or rejected the run."""


def _headers(token: str | None, directory: str | None = None) -> dict[str, str]:
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if directory:
        headers[DIRECTORY_HEADER] = directory
    return headers


def check_health(base_url: str, token: str | None = None) -> dict[str, Any]:
    """Probe ``GET /health``; returns the payload or raises RemoteServerError."""
    try:
        response = httpx.get(f"{base_url.rstrip('/')}/health", headers=_headers(token), timeout=10.0)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as e:
        raise RemoteServerError(f"server at {base_url} is not reachable: {e}") from e
    if payload.get("status") != "ok":
        raise RemoteServerError(f"server at {base_url} reported status {payload.get('status')!r}")
    return payload


async def run_journey_remote(
    base_url: str,
    token: str | None,
    directory: str,
    request: JourneyAnalyseRequest,
) -> dict[str, Any]:
    """Run the canned journey analysis on a remote server.

    Subscribes to ``/event`` before POSTing ``/journey/analyse`` (so no
    progress is missed), folds the stream into status lines, and returns
    the finished run's artifact part properties (``path``, ``summary``).
    Paths in ``request`` are interpreted on the *server's* filesystem.
    Cancellation aborts the remote session tree before propagating.
    """
    base_url = base_url.rstrip("/")
    session_id: str | None = None
    async with httpx.AsyncClient(base_url=base_url, headers=_headers(token), timeout=httpx.Timeout(30.0)) as client:
        try:
            async with client.stream(
                "GET", "/event", headers=_headers(token, directory), timeout=httpx.Timeout(30.0, read=None)
            ) as stream:
                if stream.status_code != 200:
                    raise RemoteServerError(f"event stream refused: HTTP {stream.status_code}")

                post = asyncio.create_task(
                    client.post(
                        "/journey/analyse",
                        json=request.model_dump(mode="json", by_alias=True),
                        headers=_headers(token, directory),
                    )
                )
                try:
                    tracker = _RunTracker()
                    pending: list[dict[str, Any]] = []
                    async for event in _sse_events(stream):
                        if session_id is None:
                            pending.append(event)
                            if post.done():
                                session_id = _session_from_response(post.result())
                                tracker.session_id = session_id
                                for buffered in pending:
                                    if tracker.handle(buffered):
                                        return await _fetch_artifact(client, token, session_id)
                                pending.clear()
                            continue
                        if tracker.handle(event):
                            return await _fetch_artifact(client, token, session_id)
                    raise RemoteServerError("event stream ended before the run finished")
                finally:
                    if not post.done():
                        post.cancel()
                    await asyncio.gather(post, return_exceptions=True)
        except asyncio.CancelledError:
            if session_id is not None:
                await asyncio.shield(_abort(base_url, token, session_id))
            raise


def _session_from_response(response: httpx.Response) -> str:
    if response.status_code == 503:
        raise RemoteServerError(f"server has no LLM credentials configured: {_detail(response)}")
    if response.status_code != 202:
        raise RemoteServerError(f"analyse request failed: HTTP {response.status_code}: {_detail(response)}")
    session_id = response.json().get("sessionId")
    if not session_id:
        raise RemoteServerError("analyse response carried no sessionId")
    status(f"remote run started (session {session_id})")
    return session_id


def _detail(response: httpx.Response) -> str:
    try:
        return str(response.json().get("detail", response.text))
    except Exception:  # noqa: BLE001
        return response.text


class _RunTracker:
    """Folds bus events for one session tree into status lines.

    ``handle`` returns True when the root session finished successfully and
    raises :class:`RemoteServerError` when it errored.
    """

    def __init__(self) -> None:
        self.session_id: str | None = None
        self._children: dict[str, str] = {}  # child session id -> agent name
        self._features = 0

    def _mine(self, sid: str | None) -> bool:
        return sid is not None and (sid == self.session_id or sid in self._children)

    def handle(self, event: dict[str, Any]) -> bool:
        kind = event.get("type")
        properties = event.get("properties") or {}
        if kind == "session.created":
            session = properties.get("session") or {}
            if session.get("parentId") == self.session_id:
                self._children[session["id"]] = session.get("agent", "?")
                status(f"subagent started: {session.get('agent', '?')} — {session.get('title') or session['id']}")
        elif kind == "session.idle":
            session = properties.get("session") or {}
            agent = self._children.get(session.get("id", ""))
            if agent is not None:
                status(f"subagent finished: {agent}")
            elif session.get("id") == self.session_id:
                status(f"run finished — {self._features} feature(s) emitted")
                return True
        elif kind == "session.error":
            session = properties.get("session") or {}
            if self._mine(session.get("id")):
                raise RemoteServerError(f"remote run failed: {properties.get('error') or 'unknown error'}")
        elif kind == "part.created":
            part = properties.get("part") or {}
            if not self._mine(part.get("sessionId")):
                return False
            if part.get("type") == "feature":
                self._features += 1
                proposed = (part.get("feature") or {}).get("proposedId", "?")
                status(f"feature: {proposed}")
            elif part.get("type") == "tool" and part.get("sessionId") == self.session_id:
                status(f"tool started: {part.get('tool', '?')}")
        elif kind == "part.updated":
            part = properties.get("part") or {}
            if part.get("type") == "tool" and part.get("sessionId") == self.session_id:
                state = (part.get("state") or {}).get("status", "?")
                if state in ("completed", "error"):
                    status(f"tool {state}: {part.get('tool', '?')}")
        return False


async def _sse_events(stream: httpx.Response):
    """Decode ``data:``-framed SSE into event dicts (the phase-4 contract)."""
    data: list[str] = []
    size = 0
    async for line in stream.aiter_lines():
        if not line.strip():
            if data:
                payload, size = "\n".join(data), 0
                data.clear()
                try:
                    event = json.loads(payload)
                except json.JSONDecodeError:
                    warning("skipping unparseable event frame")
                    continue
                if isinstance(event, dict):
                    yield event
            continue
        if line.startswith("data:"):
            chunk = line[5:].removeprefix(" ")
            size += len(chunk)
            if size > _MAX_EVENT_SIZE:
                raise RemoteServerError("event frame exceeds size cap — broken stream")
            data.append(chunk)


async def _fetch_artifact(client: httpx.AsyncClient, token: str | None, session_id: str) -> dict[str, Any]:
    """The run's final artifact part — intermediate artifacts (the
    features.yaml feature map) precede the journey.yaml deliverable."""
    response = await client.get(f"/session/{session_id}/message", headers=_headers(token))
    response.raise_for_status()
    artifact: dict[str, Any] | None = None
    for message in response.json():
        for part in message.get("parts", []):
            if part.get("type") == "artifact":
                artifact = part
    if artifact is None:
        raise RemoteServerError("run finished but produced no artifact part")
    return artifact


async def _abort(base_url: str, token: str | None, session_id: str) -> None:
    """Best-effort abort on a fresh connection (ours may be mid-stream)."""
    try:
        async with httpx.AsyncClient(base_url=base_url, headers=_headers(token), timeout=10.0) as client:
            await client.post(f"/session/{session_id}/abort")
        status(f"remote run aborted (session {session_id})")
    except httpx.HTTPError as e:  # noqa: BLE001 — abort is best-effort
        warning(f"could not abort remote session {session_id}: {e}")
