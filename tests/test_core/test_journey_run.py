"""Tests for the canned journey run (main agent + task tool + finalize)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import yaml

from skene.core.embedded import run_journey_embedded
from skene.core.journey import JourneyRequestError, JourneyRunError, start_journey_run
from skene.schema import (
    ArtifactPart,
    JourneyAnalyseRequest,
    MilestonePart,
    ToolPart,
)
from tests.fakes import JourneyFakeLLM, ScriptedClient, turn

PARITY = Path(__file__).parent.parent / "fixtures" / "parity"


def _parity_request(output: Path) -> JourneyAnalyseRequest:
    return JourneyAnalyseRequest(
        path=str(PARITY / "repo"),
        schema_dir=str(PARITY / "schemas"),
        product_name="ParityProduct",
        output=str(output),
        specialize=False,
        classify_concurrency=2,
    )


async def test_journey_run_spawns_subagents_and_emits_artifact(services, workspace, tmp_path):
    output = tmp_path / "out" / "journey.yaml"
    handle = await start_journey_run(
        services.sessions, services.registry, str(workspace), _parity_request(output), llm=JourneyFakeLLM()
    )
    journey = await asyncio.wait_for(handle.result, timeout=5)
    await services.sessions.wait(handle.session.id)

    assert journey.product.name == "ParityProduct"
    assert output.is_file()

    session = await services.store.get_session(handle.session.id)
    assert session.status == "idle"
    assert session.agent == "skene"

    # Parent trace: canned prompt, then task × 2 + finalize + artifact.
    messages = await services.store.list_messages(session.id)
    assert [type(m).__name__ for m, _ in messages] == ["UserMessage", "AssistantMessage"]
    assistant, parts = messages[1]
    assert assistant.finish == "no_tool_calls"
    tool_parts = [p for p in parts if isinstance(p, ToolPart)]
    assert sorted(p.tool for p in tool_parts) == ["finalize_journey", "task", "task"]
    assert all(p.state.status == "completed" for p in tool_parts)
    artifacts = [p for p in parts if isinstance(p, ArtifactPart)]
    assert len(artifacts) == 1
    assert artifacts[0].path == str(output)

    # Child sessions: one per subagent, idle, holding the milestone parts.
    children = await services.store.list_children(session.id)
    assert sorted(c.agent for c in children) == ["code", "schema"]
    assert all(c.status == "idle" for c in children)
    milestones_by_agent = {}
    for child in children:
        child_parts = [p for _, ps in await services.store.list_messages(child.id) for p in ps]
        milestones_by_agent[child.agent] = [p.milestone for p in child_parts if isinstance(p, MilestonePart)]
    assert [m.proposed_id for m in milestones_by_agent["code"]] == ["landing_page"]
    assert [m.proposed_id for m in milestones_by_agent["schema"]] == ["account_created", "invite_sent"]
    # Live parts carry the *candidate* shape: no stage yet, camelCase wire form.
    candidate = milestones_by_agent["schema"][0]
    assert candidate.stage_id is None
    assert '"proposedId"' in candidate.model_dump_json()


async def test_journey_output_matches_pipeline_golden(services, workspace, tmp_path):
    """Parity check that retired the deterministic pipeline.

    ``journey.golden.yaml`` was produced by the phase-2
    ``run_journey_pipeline`` with the same fake LLM and inputs; the
    agentic flow must reproduce it (modulo the generation timestamp).
    """
    output = tmp_path / "journey.yaml"
    handle = await start_journey_run(
        services.sessions, services.registry, str(workspace), _parity_request(output), llm=JourneyFakeLLM()
    )
    await asyncio.wait_for(handle.result, timeout=5)
    await services.sessions.wait(handle.session.id)

    produced = yaml.safe_load(output.read_text())
    golden = yaml.safe_load((PARITY / "journey.golden.yaml").read_text())
    produced["product"]["generated_at"] = golden["product"]["generated_at"]
    assert produced == golden


async def test_journey_run_errors_when_agent_never_finalizes(services, workspace):
    llm = ScriptedClient([turn(text="I have nothing to do.")])
    handle = await start_journey_run(
        services.sessions, services.registry, str(workspace), JourneyAnalyseRequest(path=str(workspace)), llm=llm
    )
    with pytest.raises(JourneyRunError, match="without calling finalize_journey"):
        await asyncio.wait_for(handle.result, timeout=5)
    await services.sessions.wait(handle.session.id)
    assert (await services.store.get_session(handle.session.id)).status == "error"


async def test_journey_run_records_run_failure(services, workspace):
    class ExplodingLLM(ScriptedClient):
        async def generate_with_tools(self, messages, tools):
            raise RuntimeError("provider exploded")

    handle = await start_journey_run(
        services.sessions,
        services.registry,
        str(workspace),
        JourneyAnalyseRequest(path=str(workspace)),
        llm=ExplodingLLM([]),
    )
    with pytest.raises(RuntimeError, match="provider exploded"):
        await asyncio.wait_for(handle.result, timeout=5)
    await services.sessions.wait(handle.session.id)

    session = await services.store.get_session(handle.session.id)
    assert session.status == "error"
    assistant = (await services.store.list_messages(session.id))[-1][0]
    assert assistant.finish == "error"
    assert "provider exploded" in assistant.error


async def test_journey_request_validation(services, workspace):
    with pytest.raises(JourneyRequestError, match="not a directory"):
        await start_journey_run(
            services.sessions,
            services.registry,
            str(workspace),
            JourneyAnalyseRequest(path=str(workspace / "missing")),
            llm=ScriptedClient([]),
        )
    with pytest.raises(JourneyRequestError, match="mutually exclusive"):
        await start_journey_run(
            services.sessions,
            services.registry,
            str(workspace),
            JourneyAnalyseRequest(schema_dir=str(workspace), db_url="postgresql://u:p@h/db"),
            llm=ScriptedClient([]),
        )


async def test_journey_run_never_persists_db_password(services, workspace, tmp_path, monkeypatch):
    from skene.analyzers.schema_parsers import postgres_live
    from skene.analyzers.schema_parsers.models import SchemaIndex

    monkeypatch.setattr(postgres_live, "introspect_db", lambda url: SchemaIndex(files={}))
    request = JourneyAnalyseRequest(
        path=str(PARITY / "repo"),
        db_url="postgresql://user:hunter2@db:5432/app",
        product_name="ParityProduct",
        output=str(tmp_path / "journey.yaml"),
        specialize=False,
    )
    handle = await start_journey_run(
        services.sessions, services.registry, str(workspace), request, llm=JourneyFakeLLM()
    )
    await asyncio.wait_for(handle.result, timeout=5)
    await services.sessions.wait(handle.session.id)

    session_ids = [handle.session.id] + [c.id for c in await services.store.list_children(handle.session.id)]
    for session_id in session_ids:
        for message, parts in await services.store.list_messages(session_id):
            assert "hunter2" not in message.model_dump_json()
            for part in parts:
                assert "hunter2" not in part.model_dump_json()


async def test_embedded_runner_round_trip(workspace, tmp_path):
    output = tmp_path / "out" / "journey.yaml"
    journey = await run_journey_embedded(
        _parity_request(output),
        JourneyFakeLLM(),
        directory=workspace,
        db_path=tmp_path / "embedded.db",
    )
    assert journey.product.name == "ParityProduct"
    assert output.is_file()
