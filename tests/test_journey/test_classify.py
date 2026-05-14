"""Tests for the Step 4 classifier."""

from __future__ import annotations

import json
from typing import AsyncGenerator

import pytest

from skene.analyzers.journey.candidate import CandidateMilestone
from skene.analyzers.journey.classify import (
    ClassificationResult,
    classify_all,
    classify_milestone,
)
from skene.analyzers.journey.models import Evidence
from skene.llm.base import LLMClient


class _FakeLLM(LLMClient):
    """Returns a queued response (or raises a queued exception) per call."""

    def __init__(self, responses: list[str | Exception]) -> None:
        self._responses = list(responses)
        self.calls: list[str] = []

    async def generate_content_with_usage(
        self, prompt: str
    ) -> tuple[str, dict[str, int] | None]:
        self.calls.append(prompt)
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
        return "fake"

    def get_provider_name(self) -> str:
        return "fake"


def _candidate(pid: str, name: str = "x") -> CandidateMilestone:
    return CandidateMilestone(
        proposed_id=pid,
        name=name,
        description=name,
        evidence=[Evidence(source="code", path="src/x.ts", reason="found")],
        confidence=0.8,
    )


@pytest.mark.asyncio
async def test_classify_milestone_parses_valid_json():
    llm = _FakeLLM([json.dumps({"stage_id": "activation", "confidence": 0.9, "reason": "ok"})])
    cm = _candidate("first_estimate", "First Estimate")
    result = await classify_milestone(cm, llm)
    assert isinstance(result, ClassificationResult)
    assert result.stage_id == "activation"
    assert result.confidence == 0.9


@pytest.mark.asyncio
async def test_classify_milestone_handles_fenced_json():
    fenced = "```json\n" + json.dumps({"stage_id": "discovery", "confidence": 0.5, "reason": "?"}) + "\n```"
    llm = _FakeLLM([fenced])
    cm = _candidate("landing")
    result = await classify_milestone(cm, llm)
    assert result.stage_id == "discovery"


@pytest.mark.asyncio
async def test_classify_milestone_raises_on_non_json():
    llm = _FakeLLM(["I think this is discovery."])
    cm = _candidate("x")
    with pytest.raises(ValueError, match="non-JSON"):
        await classify_milestone(cm, llm)


@pytest.mark.asyncio
async def test_classify_milestone_raises_on_bad_shape():
    llm = _FakeLLM([json.dumps({"stage_id": "discovery"})])  # missing fields
    cm = _candidate("x")
    with pytest.raises(ValueError, match="invalid result"):
        await classify_milestone(cm, llm)


@pytest.mark.asyncio
async def test_classify_all_assigns_stage_ids():
    responses = [
        json.dumps({"stage_id": "discovery", "confidence": 0.9, "reason": "marketing"}),
        json.dumps({"stage_id": "activation", "confidence": 0.85, "reason": "first value"}),
    ]
    llm = _FakeLLM(responses)
    cms = [_candidate("a"), _candidate("b")]
    out = await classify_all(cms, llm, concurrency=2)
    stage_ids = {cm.proposed_id: cm.stage_id for cm in out}
    assert stage_ids == {"a": "discovery", "b": "activation"}


@pytest.mark.asyncio
async def test_classify_all_confidence_is_min_of_inputs():
    # Candidate confidence is 0.8; classifier confidence is 0.95 → result 0.8
    llm = _FakeLLM(
        [json.dumps({"stage_id": "discovery", "confidence": 0.95, "reason": "x"})]
    )
    cm = _candidate("x")
    [out] = await classify_all([cm], llm)
    assert out.confidence == 0.8


@pytest.mark.asyncio
async def test_classify_all_falls_back_to_engagement_on_unknown_stage():
    llm = _FakeLLM(
        [json.dumps({"stage_id": "moon_phase", "confidence": 0.9, "reason": "?"})]
    )
    [out] = await classify_all([_candidate("x")], llm)
    assert out.stage_id == "engagement"
    assert out.confidence <= 0.3


@pytest.mark.asyncio
async def test_classify_all_falls_back_on_llm_error():
    llm = _FakeLLM([RuntimeError("network down")])
    [out] = await classify_all([_candidate("x")], llm)
    assert out.stage_id == "engagement"
    assert out.confidence <= 0.3
