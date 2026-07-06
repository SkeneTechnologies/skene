"""End-to-end tests for the HTTP API (in-process ASGI)."""

from __future__ import annotations

import httpx
import yaml

from skene.server import create_app
from tests.fakes import HangingClient, ScriptedClient, turn


async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_doc_serves_openapi(client):
    response = await client.get("/doc")
    assert response.status_code == 200
    assert "/session/{session_id}/message" in response.json()["paths"]


async def test_session_crud_and_wire_shape(client):
    created = await client.post("/session", json={"title": "hello", "agent": "skene"})
    assert created.status_code == 201
    session = created.json()
    # camelCase on the wire.
    assert session["projectId"].startswith("prj_")
    assert session["id"].startswith("ses_")
    assert session["status"] == "idle"
    assert session["parentId"] is None

    listed = await client.get("/session")
    assert [s["id"] for s in listed.json()] == [session["id"]]

    fetched = await client.get(f"/session/{session['id']}")
    assert fetched.json() == session

    assert (await client.get("/session/ses_nope")).status_code == 404

    child = await client.post("/session", json={"parentId": session["id"], "agent": "code"})
    assert child.status_code == 201
    children = await client.get(f"/session/{session['id']}/children")
    assert [s["id"] for s in children.json()] == [child.json()["id"]]

    orphan = await client.post("/session", json={"parentId": "ses_nope"})
    assert orphan.status_code == 404


async def test_unknown_body_field_is_rejected(client):
    # WireModel extra="forbid": typos fail loudly instead of being dropped.
    response = await client.post("/session", json={"tittle": "typo"})
    assert response.status_code == 422


async def test_sessions_are_scoped_by_directory_header(client, tmp_path):
    other = tmp_path / "elsewhere"
    other.mkdir()
    await client.post("/session", json={})
    scoped = await client.get("/session", headers={"x-skene-directory": str(other)})
    assert scoped.json() == []
    missing = await client.get("/session", headers={"x-skene-directory": str(other / "nope")})
    assert missing.status_code == 400


async def test_prompt_flow(client, services):
    services.sessions.llm_factory = lambda: ScriptedClient(
        [turn(text="hi there", usage={"input_tokens": 3, "output_tokens": 2})]
    )
    session_id = (await client.post("/session", json={})).json()["id"]

    accepted = await client.post(f"/session/{session_id}/message", json={"text": "hello"})
    assert accepted.status_code == 202
    assert accepted.json()["role"] == "user"

    await services.sessions.wait(session_id)

    messages = (await client.get(f"/session/{session_id}/message")).json()
    assert [m["info"]["role"] for m in messages] == ["user", "assistant"]
    assistant = messages[1]
    assert assistant["info"]["finish"] == "no_tool_calls"
    assert assistant["info"]["tokens"] == {"input": 3, "output": 2}
    assert assistant["parts"][0]["type"] == "text"
    assert assistant["parts"][0]["text"] == "hi there"

    assert (await client.post("/session/ses_nope/message", json={"text": "x"})).status_code == 404
    assert (await client.get("/session/ses_nope/message")).status_code == 404


async def test_prompt_busy_and_abort(client, services):
    hanging = HangingClient()
    services.sessions.llm_factory = lambda: hanging
    session_id = (await client.post("/session", json={})).json()["id"]

    assert (await client.post(f"/session/{session_id}/message", json={"text": "one"})).status_code == 202
    await hanging.called.wait()
    assert (await client.post(f"/session/{session_id}/message", json={"text": "two"})).status_code == 409

    aborted = await client.post(f"/session/{session_id}/abort")
    assert aborted.json() == {"aborted": True}
    assert (await client.get(f"/session/{session_id}")).json()["status"] == "idle"
    assert (await client.post(f"/session/{session_id}/abort")).json() == {"aborted": False}
    assert (await client.post("/session/ses_nope/abort")).status_code == 404


async def test_journey_analyse_validates_request(client, workspace):
    bad = await client.post("/journey/analyse", json={"path": str(workspace / "missing")})
    assert bad.status_code == 400
    both = await client.post("/journey/analyse", json={"schemaDir": str(workspace), "dbUrl": "postgresql://u:p@h/db"})
    assert both.status_code == 400


async def test_journey_analyse_starts_session(client, services, workspace, monkeypatch):
    import skene.core.journey as journey_module
    from tests.fakes import make_journey

    async def fake(cfg, llm):
        return make_journey()

    monkeypatch.setattr(journey_module, "run_journey_pipeline", fake)
    services.sessions.llm_factory = lambda: ScriptedClient([])

    accepted = await client.post("/journey/analyse", json={"path": str(workspace)})
    assert accepted.status_code == 202
    session_id = accepted.json()["sessionId"]
    await services.sessions.wait(session_id)

    session = (await client.get(f"/session/{session_id}")).json()
    assert session["status"] == "idle"
    assert session["agent"] == "journey"

    journey = await client.get("/journey")
    assert journey.status_code == 200
    assert journey.json()["product"]["name"] == "TestProduct"


async def test_get_journey_404_when_absent(client):
    assert (await client.get("/journey")).status_code == 404


async def test_get_journey_reads_existing_yaml(client, workspace):
    bundle = workspace / "skene-context"
    bundle.mkdir()
    (bundle / "journey.yaml").write_text(yaml.safe_dump({"product": {"name": "P"}}))
    response = await client.get("/journey")
    assert response.json()["product"]["name"] == "P"


async def test_bearer_auth(services, workspace):
    app = create_app(services, auth_token="sekrit")
    transport = httpx.ASGITransport(app=app)
    headers = {"x-skene-directory": str(workspace)}
    async with httpx.AsyncClient(transport=transport, base_url="http://skene.test", headers=headers) as client:
        assert (await client.get("/session")).status_code == 401
        assert (await client.get("/session", headers={"Authorization": "Bearer wrong"})).status_code == 401
        ok = await client.get("/session", headers={"Authorization": "Bearer sekrit"})
        assert ok.status_code == 200
        # /health stays open for probes.
        assert (await client.get("/health")).status_code == 200


async def test_journey_analyse_503_when_no_llm_configured(client, services, workspace):
    def broken_factory():
        raise RuntimeError("no LLM configured")

    services.sessions.llm_factory = broken_factory
    response = await client.post("/journey/analyse", json={"path": str(workspace)})
    assert response.status_code == 503
    # Failing fast means no orphan session was created.
    assert (await client.get("/session")).json() == []
