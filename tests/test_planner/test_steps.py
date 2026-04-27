"""Tests for planner step definitions and loading."""

import json
from unittest.mock import AsyncMock

import pytest

from skene.planner.steps import (
    DEFAULT_PLAN_STEPS,
    PlanStepDefinition,
    PlanStepsParseError,
    load_plan_steps,
    load_plan_steps_file,
    parse_plan_steps_with_llm,
)


class TestPlanStepDefinition:
    def test_dataclass_fields(self):
        step = PlanStepDefinition(title="Test Title", instruction="Test instruction.")
        assert step.title == "Test Title"
        assert step.instruction == "Test instruction."


class TestDefaultPlanSteps:
    def test_has_four_steps(self):
        assert len(DEFAULT_PLAN_STEPS) == 4

    def test_all_have_titles_and_instructions(self):
        for step in DEFAULT_PLAN_STEPS:
            assert step.title
            assert step.instruction


class TestParsePlanStepsWithLlm:
    @pytest.mark.asyncio
    async def test_parses_valid_json_array(self):
        llm = AsyncMock()
        llm.generate_content = AsyncMock(
            return_value=json.dumps(
                [
                    {"title": "Core Analysis", "instruction": "Strip to fundamentals."},
                    {"title": "The Playbook", "instruction": "Identify elite moves."},
                ]
            )
        )
        steps = await parse_plan_steps_with_llm(llm, "# My Plan\n- Core\n- Playbook")
        assert len(steps) == 2
        assert steps[0].title == "Core Analysis"
        assert steps[1].instruction == "Identify elite moves."

    @pytest.mark.asyncio
    async def test_strips_code_fences(self):
        llm = AsyncMock()
        payload = json.dumps(
            [
                {"title": "Step A", "instruction": "Do this."},
                {"title": "Step B", "instruction": "Do that."},
            ]
        )
        llm.generate_content = AsyncMock(return_value=f"```json\n{payload}\n```")
        steps = await parse_plan_steps_with_llm(llm, "content")
        assert len(steps) == 2
        assert steps[0].title == "Step A"

    @pytest.mark.asyncio
    async def test_raises_on_invalid_json(self):
        llm = AsyncMock()
        llm.generate_content = AsyncMock(return_value="not json at all")
        with pytest.raises(PlanStepsParseError, match="invalid JSON"):
            await parse_plan_steps_with_llm(llm, "content")

    @pytest.mark.asyncio
    async def test_raises_on_too_many_steps(self):
        llm = AsyncMock()
        llm.generate_content = AsyncMock(
            return_value=json.dumps([{"title": f"Step {i}", "instruction": f"Do step {i}."} for i in range(5)])
        )
        with pytest.raises(PlanStepsParseError, match="Expected 0-4 steps"):
            await parse_plan_steps_with_llm(llm, "content")

    @pytest.mark.asyncio
    async def test_accepts_single_step(self):
        llm = AsyncMock()
        llm.generate_content = AsyncMock(
            return_value=json.dumps([{"title": "Only One", "instruction": "Single step."}])
        )
        steps = await parse_plan_steps_with_llm(llm, "content")
        assert len(steps) == 1
        assert steps[0].title == "Only One"

    @pytest.mark.asyncio
    async def test_raises_on_missing_fields(self):
        llm = AsyncMock()
        llm.generate_content = AsyncMock(
            return_value=json.dumps(
                [
                    {"title": "OK Step", "instruction": "Fine."},
                    {"title": "Missing instruction"},
                ]
            )
        )
        with pytest.raises(PlanStepsParseError, match="missing title or instruction"):
            await parse_plan_steps_with_llm(llm, "content")

    @pytest.mark.asyncio
    async def test_raises_on_llm_failure(self):
        llm = AsyncMock()
        llm.generate_content = AsyncMock(side_effect=RuntimeError("Connection refused"))
        with pytest.raises(PlanStepsParseError, match="LLM call failed"):
            await parse_plan_steps_with_llm(llm, "content")

    @pytest.mark.asyncio
    async def test_filters_reserved_titles(self):
        """Technical Execution and Executive Summary are added automatically; filter from LLM output."""
        llm = AsyncMock()
        llm.generate_content = AsyncMock(
            return_value=json.dumps(
                [
                    {"title": "Marketing Strategy", "instruction": "Define campaign."},
                    {"title": "Technical Execution", "instruction": "Build the system."},
                    {"title": "Executive Summary", "instruction": "Summarize."},
                ]
            )
        )
        steps = await parse_plan_steps_with_llm(llm, "content")
        assert len(steps) == 1
        assert steps[0].title == "Marketing Strategy"


class TestLoadPlanStepsFile:
    def test_returns_none_when_no_file(self, tmp_path):
        result = load_plan_steps_file(tmp_path)
        assert result is None

    def test_reads_file_from_context_dir(self, tmp_path):
        plan_file = tmp_path / "plan-steps.md"
        plan_file.write_text("## Core\nAnalysis step.")
        result = load_plan_steps_file(tmp_path)
        assert result == "## Core\nAnalysis step."

    def test_returns_none_when_context_dir_is_none_and_no_default(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = load_plan_steps_file(None)
        assert result is None

    def test_reads_from_default_skene_context_bundle(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        bundle = tmp_path / "skene-context"
        bundle.mkdir()
        plan_file = bundle / "plan-steps.md"
        plan_file.write_text("# Default steps")
        result = load_plan_steps_file(None)
        assert result == "# Default steps"

    def test_falls_back_to_legacy_skene_bundle(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        legacy = tmp_path / "skene"
        legacy.mkdir()
        (legacy / "plan-steps.md").write_text("# Legacy steps")
        result = load_plan_steps_file(None)
        assert result == "# Legacy steps"


class TestLoadPlanSteps:
    @pytest.mark.asyncio
    async def test_returns_defaults_when_no_file(self, tmp_path):
        steps = await load_plan_steps(context_dir=tmp_path, llm=None)
        assert steps == DEFAULT_PLAN_STEPS

    @pytest.mark.asyncio
    async def test_returns_defaults_when_llm_is_none(self, tmp_path):
        plan_file = tmp_path / "plan-steps.md"
        plan_file.write_text("## Core\nDo analysis.")
        steps = await load_plan_steps(context_dir=tmp_path, llm=None)
        assert steps == DEFAULT_PLAN_STEPS

    @pytest.mark.asyncio
    async def test_parses_file_when_llm_provided(self, tmp_path):
        plan_file = tmp_path / "plan-steps.md"
        plan_file.write_text("## Core\nDo analysis.")
        llm = AsyncMock()
        llm.generate_content = AsyncMock(
            return_value=json.dumps(
                [
                    {"title": "Core", "instruction": "Do analysis."},
                    {"title": "Playbook", "instruction": "Identify moves."},
                ]
            )
        )
        steps = await load_plan_steps(context_dir=tmp_path, llm=llm)
        assert len(steps) == 2
        assert steps[0].title == "Core"
