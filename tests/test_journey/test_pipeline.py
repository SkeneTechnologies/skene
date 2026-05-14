"""End-to-end smoke tests for the journey pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import AsyncGenerator

import pytest

from skene.analyzers.journey.models import Journey
from skene.analyzers.journey.pipeline import (
    JourneyPipelineConfig,
    run_journey_pipeline,
)
from skene.analyzers.journey.serialize import write as write_journey
from skene.llm.agent_loop import AssistantTurn, Message, Tool, ToolCall
from skene.llm.base import LLMClient


class _PipelineFakeLLM(LLMClient):
    """Returns canned agent turns for schema + code, and a classify JSON
    for every text-only ``generate_content`` call.

    The fake is dumb on purpose: it inspects messages to decide which
    agent is asking. Schema agent sees DB-flavored instructions; code
    agent sees code-flavored instructions. Both eventually stop.
    """

    def __init__(self, classify_stage: str = "discovery"):
        self._classify_stage = classify_stage
        self._schema_step = 0
        self._code_step = 0

    async def generate_content_with_usage(
        self, prompt: str
    ) -> tuple[str, dict[str, int] | None]:
        # Used by specialize (we'll force --no-specialize) and classify.
        # Always answer with a discovery classification.
        return (
            json.dumps(
                {
                    "stage_id": self._classify_stage,
                    "confidence": 0.85,
                    "reason": "fake classifier",
                }
            ),
            None,
        )

    async def generate_content_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        if False:
            yield ""
        raise NotImplementedError

    def get_model_name(self) -> str:
        return "fake"

    def get_provider_name(self) -> str:
        return "fake"

    async def generate_with_tools(
        self, messages: list[Message], tools: list[Tool]
    ) -> AssistantTurn:
        # Distinguish agents by the system prompt
        system = (messages[0].content or "") if messages else ""
        if "parsed database schema" in system:
            return self._schema_turn()
        return self._code_turn()

    def _schema_turn(self) -> AssistantTurn:
        self._schema_step += 1
        if self._schema_step == 1:
            return AssistantTurn(
                text=None,
                tool_calls=[ToolCall(id="s1", name="list_schema_files", arguments={})],
            )
        if self._schema_step == 2:
            return AssistantTurn(
                text=None,
                tool_calls=[
                    ToolCall(
                        id="s2",
                        name="emit_milestone",
                        arguments={
                            "proposed_id": "account_created",
                            "name": "Account Created",
                            "description": "users table row inserted",
                            "table": "public.users",
                            "reason": "users table holds account state",
                            "confidence": 0.9,
                        },
                    )
                ],
            )
        return AssistantTurn(text="schema done")

    def _code_turn(self) -> AssistantTurn:
        self._code_step += 1
        if self._code_step == 1:
            return AssistantTurn(
                text=None,
                tool_calls=[ToolCall(id="c1", name="list_directory", arguments={})],
            )
        if self._code_step == 2:
            return AssistantTurn(
                text=None,
                tool_calls=[
                    ToolCall(
                        id="c2",
                        name="emit_milestone",
                        arguments={
                            "proposed_id": "landing_page",
                            "name": "Landing Page",
                            "description": "marketing route",
                            "path": "index.tsx",
                            "reason": "served at /",
                            "confidence": 0.9,
                        },
                    )
                ],
            )
        return AssistantTurn(text="code done")


def _build_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "index.tsx").write_text("export default () => <h1>Hi</h1>;\n")
    return repo


def _build_schema_dir(tmp_path: Path) -> Path:
    sdir = tmp_path / "schemas"
    sdir.mkdir()
    (sdir / "public.sql").write_text(
        "CREATE TABLE users (id uuid PRIMARY KEY, email text NOT NULL);\n"
    )
    return sdir


@pytest.mark.asyncio
async def test_pipeline_both_sources(tmp_path: Path):
    repo = _build_repo(tmp_path)
    schemas = _build_schema_dir(tmp_path)
    cfg = JourneyPipelineConfig(
        repo_root=repo,
        schema_dir=schemas,
        product_name="TestProduct",
        specialize=False,  # skip — fake LLM would need to return SpecializedStages
        classify_concurrency=2,
    )
    llm = _PipelineFakeLLM(classify_stage="discovery")
    journey = await run_journey_pipeline(cfg, llm)

    assert isinstance(journey, Journey)
    assert journey.product.name == "TestProduct"
    # Both candidates classified as discovery → one stage with two milestones
    assert len(journey.stages) == 1
    assert journey.stages[0].id == "discovery"
    milestone_ids = {m.id for m in journey.stages[0].milestones}
    assert milestone_ids == {"account_created", "landing_page"}


@pytest.mark.asyncio
async def test_pipeline_schema_only(tmp_path: Path):
    schemas = _build_schema_dir(tmp_path)
    cfg = JourneyPipelineConfig(
        repo_root=None,
        schema_dir=schemas,
        product_name="SchemaOnly",
        specialize=True,  # should auto-skip because there's no repo
        classify_concurrency=2,
    )
    llm = _PipelineFakeLLM(classify_stage="onboarding")
    journey = await run_journey_pipeline(cfg, llm)
    # Only the schema agent ran → one milestone, classified into onboarding
    assert [s.id for s in journey.stages] == ["onboarding"]
    assert len(journey.stages[0].milestones) == 1


@pytest.mark.asyncio
async def test_pipeline_code_only(tmp_path: Path):
    repo = _build_repo(tmp_path)
    cfg = JourneyPipelineConfig(
        repo_root=repo,
        schema_dir=None,
        product_name="CodeOnly",
        specialize=False,
        classify_concurrency=2,
    )
    llm = _PipelineFakeLLM(classify_stage="activation")
    journey = await run_journey_pipeline(cfg, llm)
    assert [s.id for s in journey.stages] == ["activation"]
    assert len(journey.stages[0].milestones) == 1


def test_pipeline_config_requires_at_least_one_input():
    with pytest.raises(ValueError, match="at least one"):
        JourneyPipelineConfig(
            repo_root=None,
            schema_dir=None,
            product_name="X",
        )


@pytest.mark.asyncio
async def test_pipeline_output_writes_yaml_with_from_alias(tmp_path: Path):
    repo = _build_repo(tmp_path)
    cfg = JourneyPipelineConfig(
        repo_root=repo,
        schema_dir=None,
        product_name="Test",
        specialize=False,
    )
    journey = await run_journey_pipeline(cfg, _PipelineFakeLLM())
    out = tmp_path / "out.yaml"
    write_journey(journey, out)
    text = out.read_text()
    assert "product:" in text
    assert "stages:" in text
    # Layer for discovery is present
    assert "L1" in text
