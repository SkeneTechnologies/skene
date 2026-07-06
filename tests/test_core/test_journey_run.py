"""Tests for the canned journey run (session wrapper around the pipeline)."""

from __future__ import annotations

import asyncio

import pytest
import yaml

import skene.core.journey as journey_module
from skene.core.embedded import run_journey_embedded
from skene.core.journey import JourneyRequestError, start_journey_run
from skene.schema import (
    ArtifactPart,
    JourneyAnalyseRequest,
    MilestonePart,
    ToolPart,
)
from tests.fakes import ScriptedClient, make_journey


@pytest.fixture
def fake_pipeline(monkeypatch):
    """Replace the real (LLM-driven) pipeline with an instant fake."""
    calls = []

    async def fake(cfg, llm):
        calls.append(cfg)
        return make_journey()

    monkeypatch.setattr(journey_module, "run_journey_pipeline", fake)
    return calls


async def test_journey_run_emits_parts_and_artifact(services, workspace, fake_pipeline):
    request = JourneyAnalyseRequest(path=str(workspace))
    handle = await start_journey_run(services.sessions, str(workspace), request, llm=ScriptedClient([]))
    journey = await asyncio.wait_for(handle.result, timeout=5)
    await services.sessions.wait(handle.session.id)

    assert journey.product.name == "TestProduct"
    output = workspace / "skene-context" / "journey.yaml"
    assert output.is_file()
    assert yaml.safe_load(output.read_text())["product"]["name"] == "TestProduct"

    session = await services.store.get_session(handle.session.id)
    assert session.status == "idle"
    assert session.agent == "journey"

    messages = await services.store.list_messages(session.id)
    assert [type(m).__name__ for m, _ in messages] == ["UserMessage", "AssistantMessage"]
    assistant, parts = messages[1]
    assert assistant.finish == "completed"

    tool_parts = [p for p in parts if isinstance(p, ToolPart)]
    assert len(tool_parts) == 1
    assert tool_parts[0].state.status == "completed"

    milestones = [p for p in parts if isinstance(p, MilestonePart)]
    assert len(milestones) == 1
    assert milestones[0].milestone["stage_id"] == "onboarding"
    assert milestones[0].milestone["id"] == "signs_up"

    artifacts = [p for p in parts if isinstance(p, ArtifactPart)]
    assert len(artifacts) == 1
    assert artifacts[0].path == str(output)

    # Config passed through to the pipeline.
    (cfg,) = fake_pipeline
    assert cfg.repo_root == workspace.resolve()
    assert cfg.product_name == workspace.name


async def test_journey_run_records_pipeline_failure(services, workspace, monkeypatch):
    async def explode(cfg, llm):
        raise RuntimeError("pipeline exploded")

    monkeypatch.setattr(journey_module, "run_journey_pipeline", explode)
    handle = await start_journey_run(
        services.sessions, str(workspace), JourneyAnalyseRequest(path=str(workspace)), llm=ScriptedClient([])
    )
    with pytest.raises(RuntimeError, match="pipeline exploded"):
        await asyncio.wait_for(handle.result, timeout=5)
    await services.sessions.wait(handle.session.id)

    session = await services.store.get_session(handle.session.id)
    assert session.status == "error"
    assistant, parts = (await services.store.list_messages(session.id))[-1]
    assert assistant.finish == "error"
    tool_part = next(p for p in parts if isinstance(p, ToolPart))
    assert tool_part.state.status == "error"
    assert "pipeline exploded" in tool_part.state.error


async def test_journey_request_validation(services, workspace):
    with pytest.raises(JourneyRequestError, match="not a directory"):
        await start_journey_run(
            services.sessions,
            str(workspace),
            JourneyAnalyseRequest(path=str(workspace / "missing")),
            llm=ScriptedClient([]),
        )
    with pytest.raises(JourneyRequestError, match="mutually exclusive"):
        await start_journey_run(
            services.sessions,
            str(workspace),
            JourneyAnalyseRequest(schema_dir=str(workspace), db_url="postgresql://u:p@h/db"),
            llm=ScriptedClient([]),
        )


async def test_journey_user_prompt_never_contains_db_password(services, workspace, fake_pipeline, monkeypatch):
    monkeypatch.setattr(journey_module.asyncio, "to_thread", lambda fn, *a: _fake_index())
    request = JourneyAnalyseRequest(path=str(workspace), db_url="postgresql://user:hunter2@db:5432/app")
    handle = await start_journey_run(services.sessions, str(workspace), request, llm=ScriptedClient([]))
    await asyncio.wait_for(handle.result, timeout=5)
    await services.sessions.wait(handle.session.id)

    for message, parts in await services.store.list_messages(handle.session.id):
        for part in parts:
            assert "hunter2" not in part.model_dump_json()


async def _fake_index():
    from skene.analyzers.schema_parsers.models import SchemaIndex

    return SchemaIndex(files={})


async def test_embedded_runner_round_trip(workspace, tmp_path, monkeypatch):
    async def fake(cfg, llm):
        return make_journey()

    monkeypatch.setattr(journey_module, "run_journey_pipeline", fake)
    output = tmp_path / "out" / "journey.yaml"
    journey = await run_journey_embedded(
        JourneyAnalyseRequest(path=str(workspace), output=str(output)),
        ScriptedClient([]),
        directory=workspace,
        db_path=tmp_path / "embedded.db",
    )
    assert journey.product.name == "TestProduct"
    assert output.is_file()
