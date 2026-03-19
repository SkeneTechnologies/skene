"""Tests for multi-step Planner orchestration."""

import json
from unittest.mock import AsyncMock

import pytest

from skene.planner.planner import Planner
from skene.planner.schema import GrowthPlan
from skene.planner.steps import PlanStepDefinition

_MANIFEST = {
    "project_name": "TestProject",
    "description": "A test product.",
}

_TWO_STEPS = [
    PlanStepDefinition(title="Step One", instruction="Do step one."),
    PlanStepDefinition(title="Step Two", instruction="Do step two."),
]


def _make_llm(responses: list[str]) -> AsyncMock:
    """Create an LLM mock. All responses go to generate_content_with_usage."""
    llm = AsyncMock()
    llm.generate_content_with_usage = AsyncMock(side_effect=[(r, None) for r in responses])
    return llm


def _section_response(title: str, content: str) -> str:
    return json.dumps({"title": title, "content": content})


def _tech_exec_response() -> str:
    return json.dumps(
        {
            "overview": "Build the activation loop. Confidence: 85%",
            "what_we_building": "1. Item A\n2. Item B",
            "tasks": "1. Step A\n2. Step B",
            "data_triggers": "Event X fires.",
            "success_metrics": "Conversion rate >15%",
        }
    )


class TestGenerateGrowthPlan:
    @pytest.mark.asyncio
    async def test_calls_llm_for_each_step(self):
        """Should make N+1 LLM calls: N steps + tech exec (exec summary disabled)."""
        responses = [
            _section_response("Step One", "Content one."),
            _section_response("Step Two", "Content two."),
            _tech_exec_response(),
        ]
        llm = _make_llm(responses)
        planner = Planner()
        markdown, plan = await planner.generate_growth_plan(
            llm=llm,
            manifest_data=_MANIFEST,
            plan_steps=_TWO_STEPS,
        )
        assert llm.generate_content_with_usage.call_count == 3  # 2 sections + tech_exec
        assert isinstance(plan, GrowthPlan)
        assert plan.executive_summary == ""
        assert len(plan.sections) == 2
        assert plan.sections[0].title == "Step One"

    @pytest.mark.asyncio
    async def test_on_step_callback_called_for_each_section(self):
        """on_step should be called N+1 times (steps + tech exec; exec summary disabled)."""
        responses = [
            _section_response("Step One", "C."),
            _tech_exec_response(),
        ]
        llm = _make_llm(responses)
        planner = Planner()
        step_calls: list[tuple[int, str, str]] = []

        def on_step(step_number: int, title: str, chunk: str, usage: dict | None = None) -> None:
            step_calls.append((step_number, title, chunk))

        await planner.generate_growth_plan(
            llm=llm,
            manifest_data=_MANIFEST,
            plan_steps=[PlanStepDefinition(title="Step One", instruction="Do step one.")],
            on_step=on_step,
        )
        assert len(step_calls) == 2  # 1 step + tech exec
        assert step_calls[0][1] == "Step One"
        assert step_calls[1][1] == "Technical Execution"

    @pytest.mark.asyncio
    async def test_uses_default_steps_when_none_provided(self):
        """Should use DEFAULT_PLAN_STEPS (4 steps) when plan_steps is not given."""
        from skene.planner.steps import DEFAULT_PLAN_STEPS

        responses = [_section_response(s.title, "content") for s in DEFAULT_PLAN_STEPS] + [_tech_exec_response()]
        llm = _make_llm(responses)
        planner = Planner()
        _, plan = await planner.generate_growth_plan(llm=llm, manifest_data=_MANIFEST)
        assert llm.generate_content_with_usage.call_count == 5  # 4 sections + tech_exec
        assert len(plan.sections) == 4

    @pytest.mark.asyncio
    async def test_returns_markdown_string(self):
        """generate_growth_plan should return a non-empty markdown string."""
        responses = [
            _section_response("Step One", "Content."),
            _tech_exec_response(),
        ]
        llm = _make_llm(responses)
        planner = Planner()
        markdown, _ = await planner.generate_growth_plan(
            llm=llm,
            manifest_data=_MANIFEST,
            plan_steps=[PlanStepDefinition(title="Step One", instruction="Do step one.")],
        )
        assert isinstance(markdown, str)
        assert "Technical Execution" in markdown
