"""End-to-end test for the remote journey client (`skene attach` path).

Runs a real uvicorn server on a loopback port — the SSE stream can't be
exercised through httpx's buffering ASGITransport (see the phase-2 note in
docs/design/backend-server.md).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import uvicorn

from skene.cli.remote import RemoteServerError, check_health, run_journey_remote
from skene.core.services import create_services
from skene.schema import JourneyAnalyseRequest
from skene.server import create_app
from tests.fakes import JourneyFakeLLM


@pytest.fixture
async def live_server(tmp_path: Path):
    services = await create_services(tmp_path / "skene.db", llm_factory=lambda: JourneyFakeLLM())
    server = uvicorn.Server(uvicorn.Config(create_app(services), host="127.0.0.1", port=0, log_level="error"))
    task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    await task
    await services.close()


async def test_check_health_and_remote_run(live_server, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    # The fake code subagent emits a milestone whose evidence path must exist.
    (workspace / "index.tsx").write_text("export default () => null;\n")

    # check_health is sync (CLI-side); run it off-loop so it can reach the
    # uvicorn server sharing this test's event loop.
    assert (await asyncio.to_thread(check_health, live_server))["status"] == "ok"

    artifact = await run_journey_remote(
        live_server,
        None,
        str(workspace),
        JourneyAnalyseRequest(path=str(workspace), specialize=False),
    )
    assert artifact["type"] == "artifact"
    assert artifact["path"].endswith("journey.yaml")
    assert Path(artifact["path"]).is_file()
    assert "Journey assembled" in (artifact["summary"] or "")


async def test_check_health_unreachable():
    with pytest.raises(RemoteServerError, match="not reachable"):
        check_health("http://127.0.0.1:1")


async def test_remote_run_surfaces_request_errors(live_server, tmp_path):
    with pytest.raises(RemoteServerError, match="analyse request failed"):
        await run_journey_remote(
            live_server,
            None,
            str(tmp_path),
            JourneyAnalyseRequest(path=str(tmp_path / "missing")),
        )
