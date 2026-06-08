from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from skened.journey import Evidence, EvidenceSource, Journey
from skened.journey_pipeline import (
    HeuristicClassifier,
    HeuristicCodeScanner,
    JourneyPipeline,
    LlmAnalysisError,
    LlmClassifier,
)
from skened.journey_pipeline.candidate import CandidateMilestone


def test_extractor_finds_expected_signals(rich_repo: Path):
    candidates = asyncio.run(HeuristicCodeScanner().extract(rich_repo))
    names = " ".join(c.name.lower() for c in candidates)
    assert "sign up" in names or "authentication" in names
    assert "billing" in names
    assert "referral" in names
    # analytics events become their own milestones with tracked_event set
    events = {c.tracked_event for c in candidates if c.tracked_event}
    assert "signup_completed" in events
    assert "estimate_created" in events
    # every candidate has at least one code-evidence path
    assert all(c.evidence and c.evidence[0].path for c in candidates)


def test_full_pipeline_classifies_into_stages(rich_repo: Path):
    journey = asyncio.run(
        JourneyPipeline().run(rich_repo, product_name="rich", source_commit="abc123", branch="main")
    )
    assert isinstance(journey, Journey)
    assert journey.product.source_commit == "abc123"
    stage_ids = {s.id for s in journey.stages}
    # billing → expansion, referral → virality, signup/auth → discovery
    assert "expansion" in stage_ids
    assert "virality" in stage_ids
    assert "discovery" in stage_ids
    # layers are derived from present stages
    assert journey.layers
    # round-trips through validation
    Journey.model_validate_json(journey.model_dump_json(by_alias=True))


def test_pipeline_on_sparse_repo_emits_baseline(tmp_path: Path):
    repo = Path(tmp_path) / "sparse"
    repo.mkdir()
    (repo / "README.md").write_text("# nothing interesting\n")
    journey = asyncio.run(JourneyPipeline().run(repo, product_name="sparse"))
    # No signals → a single baseline discovery milestone, still a valid journey.
    assert journey.stages
    assert journey.stages[0].milestones[0].id == "entry_point"


class _FakeLLM:
    """Records prompts, returns a canned classification for every milestone."""

    def __init__(self, stage_id: str = "activation"):
        self.stage_id = stage_id
        self.calls = 0

    async def complete(self, prompt: str, *, system: str | None = None) -> str:
        self.calls += 1
        return f'```json\n{{"stage_id": "{self.stage_id}", "confidence": 0.9, "reason": "fake"}}\n```'


def test_llm_classifier_seam(rich_repo: Path):
    """The LlmClassifier drop-in works end-to-end with a fake LLM client."""
    async def run():
        candidates = await HeuristicCodeScanner().extract(rich_repo)
        fake = _FakeLLM(stage_id="activation")
        classified = await LlmClassifier(fake, concurrency=4).classify(candidates)
        assert fake.calls == len(candidates)
        assert {c.stage_id for c in classified} == {"activation"}
        # confidence is capped at the lower of extractor/classifier values
        assert all(c.confidence <= 0.9 for c in classified)

    asyncio.run(run())


class _BrokenLLM:
    async def complete(self, prompt: str, *, system: str | None = None) -> str:
        raise RuntimeError("llm down")


def test_llm_classifier_raises_on_llm_error():
    cm = CandidateMilestone(
        proposed_id="x", name="thing", description="d",
        evidence=[Evidence(source=EvidenceSource.code, path="a.py", reason="r")],
        confidence=0.8,
    )
    # An LLM failure must fail the run, not silently default to engagement.
    with pytest.raises(LlmAnalysisError):
        asyncio.run(LlmClassifier(_BrokenLLM()).classify([cm]))
