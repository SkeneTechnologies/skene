"""Tests for the milestone synthesis step (feature map → candidate milestones)."""

from __future__ import annotations

import json
from typing import AsyncGenerator

import pytest

from skene.analyzers.journey.feature import Feature
from skene.analyzers.journey.models import Evidence
from skene.analyzers.journey.synthesize import synthesize_milestones_llm
from skene.llm.base import LLMClient


class _FakeLLM(LLMClient):
    """Returns a queued response (or raises a queued exception) per call."""

    def __init__(self, responses: list[str | Exception]) -> None:
        self._responses = list(responses)
        self.prompts: list[str] = []

    async def generate_content_with_usage(self, prompt: str) -> tuple[str, dict[str, int] | None]:
        self.prompts.append(prompt)
        if not self._responses:
            raise AssertionError("fake LLM ran out of responses")
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return (nxt, None)

    async def generate_content_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        if False:
            yield ""
        raise NotImplementedError

    def get_model_name(self) -> str:
        return "synthesize-fake"

    def get_provider_name(self) -> str:
        return "fake"


def _feature(pid: str, name: str, *, source: str = "code", confidence: float = 0.8) -> Feature:
    evidence = (
        Evidence(source="code", path=f"src/{pid}.ts", reason="found")
        if source == "code"
        else Evidence(source="db", table=pid, reason="row")
    )
    return Feature(
        proposed_id=pid,
        name=name,
        description=name,
        evidence=[evidence],
        confidence=confidence,
    )


def _milestone_json(pid: str, name: str, stage_id: str, features: list[int], confidence: float = 0.9) -> dict:
    return {
        "proposed_id": pid,
        "name": name,
        "description": f"{name} description",
        "stage_id": stage_id,
        "features": features,
        "confidence": confidence,
    }


async def test_synthesis_groups_features_into_one_milestone():
    features = [
        _feature("signup_route", "Signup route", confidence=0.9),
        _feature("users_table", "Users table", source="db", confidence=0.7),
        _feature("estimates_table", "Estimates table", source="db"),
    ]
    llm = _FakeLLM(
        [
            json.dumps(
                {
                    "milestones": [
                        _milestone_json("account_created", "Account Created", "onboarding", [0, 1]),
                        _milestone_json("first_estimate", "First Estimate", "activation", [2]),
                    ]
                }
            )
        ]
    )
    out = await synthesize_milestones_llm(features, llm)
    assert [m.proposed_id for m in out] == ["account_created", "first_estimate"]
    merged = out[0]
    assert merged.stage_id == "onboarding"
    assert merged.name == "Account Created"
    # Evidence is the union of the grouped features' evidence.
    assert {ev.source.value for ev in merged.evidence} == {"code", "db"}
    # Confidence = min(LLM confidence, mean of member confidences) = min(0.9, 0.8).
    assert merged.confidence == pytest.approx(0.8)


async def test_synthesis_carries_member_tracked_event():
    f = _feature("estimates", "Estimates")
    f = f.model_copy(update={"tracked_event": "estimate_created"})
    llm = _FakeLLM(
        [json.dumps({"milestones": [_milestone_json("first_estimate", "First Estimate", "activation", [0])]})]
    )
    [out] = await synthesize_milestones_llm([f], llm)
    assert out.tracked_event == "estimate_created"


async def test_synthesis_allows_dropping_noise_features():
    features = [_feature("signup", "Signup"), _feature("noise", "Framework plumbing")]
    llm = _FakeLLM(
        [json.dumps({"milestones": [_milestone_json("account_created", "Account Created", "onboarding", [0])]})]
    )
    out = await synthesize_milestones_llm(features, llm)
    assert [m.proposed_id for m in out] == ["account_created"]


async def test_synthesis_prompt_carries_sources_and_coverage_rules():
    features = [_feature("signup", "Signup")]
    response = json.dumps({"milestones": [_milestone_json("account_created", "Account Created", "onboarding", [0])]})
    llm = _FakeLLM([response])
    await synthesize_milestones_llm(features, llm, sources="- Code repository: /repo\n- Database schema: (none)")
    [prompt] = llm.prompts
    assert "Evidence sources analysed" in prompt
    assert "- Code repository: /repo" in prompt
    assert "Coverage honesty" in prompt

    # Without sources the block is omitted but the rules remain.
    llm = _FakeLLM([response])
    await synthesize_milestones_llm(features, llm)
    [prompt] = llm.prompts
    assert "Evidence sources analysed" not in prompt
    assert "Coverage honesty" in prompt


async def test_synthesis_falls_back_on_duplicate_feature_index():
    features = [_feature("signup", "Signup"), _feature("landing", "Landing")]
    bad = json.dumps(
        {
            "milestones": [
                _milestone_json("a", "A", "onboarding", [0, 1]),
                _milestone_json("b", "B", "discovery", [1]),
            ]
        }
    )
    # Fallback: one classify call per feature.
    classify = json.dumps({"stage_id": "discovery", "confidence": 0.9, "reason": "fallback"})
    llm = _FakeLLM([bad, classify, classify])
    out = await synthesize_milestones_llm(features, llm)
    assert {m.proposed_id for m in out} == {"signup", "landing"}
    assert all(m.stage_id == "discovery" for m in out)


async def test_synthesis_falls_back_on_unknown_stage():
    features = [_feature("signup", "Signup")]
    bad = json.dumps({"milestones": [_milestone_json("a", "A", "moon_phase", [0])]})
    classify = json.dumps({"stage_id": "onboarding", "confidence": 0.9, "reason": "fallback"})
    [out] = await synthesize_milestones_llm(features, _FakeLLM([bad, classify]))
    assert out.stage_id == "onboarding"


async def test_synthesis_falls_back_on_out_of_range_index():
    features = [_feature("signup", "Signup")]
    bad = json.dumps({"milestones": [_milestone_json("a", "A", "onboarding", [5])]})
    classify = json.dumps({"stage_id": "onboarding", "confidence": 0.9, "reason": "fallback"})
    [out] = await synthesize_milestones_llm(features, _FakeLLM([bad, classify]))
    assert out.proposed_id == "signup"


async def test_synthesis_falls_back_on_non_json():
    features = [_feature("signup", "Signup")]
    classify = json.dumps({"stage_id": "discovery", "confidence": 0.9, "reason": "fallback"})
    [out] = await synthesize_milestones_llm(features, _FakeLLM(["not json", classify]))
    assert out.stage_id == "discovery"


async def test_synthesis_falls_back_on_llm_error():
    features = [_feature("signup", "Signup")]
    classify = json.dumps({"stage_id": "discovery", "confidence": 0.9, "reason": "fallback"})
    [out] = await synthesize_milestones_llm(features, _FakeLLM([RuntimeError("provider down"), classify]))
    assert out.stage_id == "discovery"
