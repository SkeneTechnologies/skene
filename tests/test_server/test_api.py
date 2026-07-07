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


async def test_doc_includes_sse_event_schemas(client):
    # The /event route streams, so FastAPI can't type it — the Event union
    # is injected by hand so generated clients (Go TUI) get the SSE types.
    spec = (await client.get("/doc")).json()
    schemas = spec["components"]["schemas"]
    assert "Event" in schemas
    for model in ("SessionCreated", "SessionError", "PartUpdated", "ServerHeartbeat"):
        assert model in schemas, model
    stream = spec["paths"]["/event"]["get"]["responses"]["200"]["content"]["text/event-stream"]
    assert stream["schema"] == {"$ref": "#/components/schemas/Event"}
    # Parts (incl. the typed milestone payload) are reachable from the spec.
    assert "MilestonePart" in schemas
    assert "CandidateMilestone" in schemas


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


async def test_journey_analyse_starts_session(client, services, workspace):
    from tests.fakes import JourneyFakeLLM

    services.sessions.llm_factory = lambda: JourneyFakeLLM()
    # The fake code subagent emits a milestone whose evidence path must exist.
    (workspace / "index.tsx").write_text("export default () => null;\n")

    accepted = await client.post("/journey/analyse", json={"path": str(workspace), "specialize": False})
    assert accepted.status_code == 202
    session_id = accepted.json()["sessionId"]
    await services.sessions.wait(session_id)

    session = (await client.get(f"/session/{session_id}")).json()
    assert session["status"] == "idle"
    assert session["agent"] == "skene"

    # The subagent child sessions are visible over HTTP.
    children = (await client.get(f"/session/{session_id}/children")).json()
    assert sorted(c["agent"] for c in children) == ["code"]

    journey = await client.get("/journey")
    assert journey.status_code == 200
    assert journey.json()["product"]["name"] == "workspace"


async def test_agent_registry_route(client):
    agents = (await client.get("/agent")).json()
    by_name = {a["name"]: a for a in agents}
    assert by_name["skene"]["mode"] == "primary"
    assert by_name["code"]["mode"] == "subagent"
    assert by_name["schema"]["mode"] == "subagent"


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


async def test_permission_ask_answer_flow(client, services):
    import asyncio

    session_id = (await client.post("/session", json={})).json()["id"]
    ask = asyncio.create_task(services.permissions.ask(session_id, tool="write_db", title="Write to users?"))
    while not (pending := (await client.get(f"/session/{session_id}/permissions")).json()):
        await asyncio.sleep(0.01)

    request = pending[0]
    assert request["status"] == "pending"
    assert request["sessionId"] == session_id
    assert request["tool"] == "write_db"

    answered = await client.post(f"/session/{session_id}/permissions/{request['id']}", json={"reply": "allow"})
    assert answered.status_code == 200
    assert answered.json()["status"] == "allowed"
    assert await ask is True

    # One-shot: a second answer conflicts.
    again = await client.post(f"/session/{session_id}/permissions/{request['id']}", json={"reply": "deny"})
    assert again.status_code == 409

    # Unknown ids and wrong sessions are 404s.
    assert (
        await client.post(f"/session/{session_id}/permissions/prm_nope", json={"reply": "allow"})
    ).status_code == 404
    other_id = (await client.post("/session", json={})).json()["id"]
    wrong = await client.post(f"/session/{other_id}/permissions/{request['id']}", json={"reply": "allow"})
    assert wrong.status_code == 404
    assert (await client.get("/session/ses_nope/permissions")).status_code == 404


async def test_config_route_without_snapshot(client):
    from skene import __version__

    config = (await client.get("/config")).json()
    assert config["version"] == __version__
    assert config["provider"] is None
    assert config["apiKeyConfigured"] is False


async def test_config_route_reports_snapshot_without_secrets(services, workspace):
    from skene.schema import ServerConfigInfo

    services.config_info = ServerConfigInfo(
        version="", provider="anthropic", model="claude-sonnet-4-5", api_key_configured=True
    )
    app = create_app(services)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://skene.test") as client:
        config = (await client.get("/config")).json()
        assert config["provider"] == "anthropic"
        assert config["apiKeyConfigured"] is True
        assert "apiKey" not in config  # only the boolean crosses the wire

        providers = (await client.get("/provider")).json()
        by_name = {p["name"]: p for p in providers}
        assert by_name["anthropic"]["active"] is True
        assert by_name["openai"]["active"] is False
        assert "gemini" in by_name


async def test_journey_analyse_503_when_no_llm_configured(client, services, workspace):
    def broken_factory():
        raise RuntimeError("no LLM configured")

    services.sessions.llm_factory = broken_factory
    response = await client.post("/journey/analyse", json={"path": str(workspace)})
    assert response.status_code == 503
    # Failing fast means no orphan session was created.
    assert (await client.get("/session")).json() == []
