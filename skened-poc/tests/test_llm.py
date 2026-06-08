from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from skened.config import Settings
from skened.journey import Journey
from skened.journey_pipeline import (
    JourneyPipeline,
    LlmBrancher,
    LlmClassifier,
    LlmCodeAgent,
    build_pipeline,
)
from skened.journey_pipeline.llm import AssistantTurn, ToolCall
from skened.models import JobStatus
from skened.service import DaemonService


class FakeLLM:
    """Scriptable fake LLMClient.

    ``chat_script`` is a list of turns; each turn is a list of (tool_name, args) tuples,
    or [] to stop. ``complete_fn`` answers text-in/text-out calls.
    """

    def __init__(self, chat_script=None, complete_fn=None):
        self.chat_script = chat_script or []
        self.complete_fn = complete_fn or (lambda prompt, system: "{}")
        self._i = 0
        self.complete_calls = 0

    async def chat(self, messages, tools=None) -> AssistantTurn:
        step = self.chat_script[self._i] if self._i < len(self.chat_script) else []
        self._i += 1
        calls = [ToolCall(id=f"c{self._i}_{j}", name=n, arguments=a) for j, (n, a) in enumerate(step)]
        raw = {"role": "assistant", "content": "" if calls else "done"}
        return AssistantTurn(text=None if calls else "done", tool_calls=calls, raw_message=raw)

    async def complete(self, prompt: str, *, system: str | None = None) -> str:
        self.complete_calls += 1
        return self.complete_fn(prompt, system)


def test_code_agent_emits_via_tool_loop(rich_repo: Path):
    llm = FakeLLM(chat_script=[
        [("list_directory", {"path": "."})],
        [("emit_milestone", {
            "proposed_id": "signup", "name": "Signup", "description": "account creation",
            "path": "app/signup/route.ts", "reason": "POST signup handler"})],
        [],  # stop
    ])
    candidates = asyncio.run(LlmCodeAgent(llm).extract(rich_repo))
    assert len(candidates) == 1
    assert candidates[0].proposed_id == "signup"
    assert candidates[0].evidence[0].path == "app/signup/route.ts"


def test_full_llm_pipeline(rich_repo: Path):
    def classify(prompt, system):
        return '{"stage_id": "discovery", "confidence": 0.9, "reason": "x"}'

    llm = FakeLLM(
        chat_script=[
            [("emit_milestone", {
                "proposed_id": "signup", "name": "Signup", "description": "d",
                "path": "app/signup/route.ts", "reason": "r"})],
            [],
        ],
        complete_fn=classify,
    )
    pipeline = JourneyPipeline(extractor=LlmCodeAgent(llm), classifier=LlmClassifier(llm))
    journey = asyncio.run(pipeline.run(rich_repo, product_name="rich", source_commit="c1"))
    assert isinstance(journey, Journey)
    assert {s.id for s in journey.stages} == {"discovery"}
    assert llm.complete_calls == 1  # one classify call for the one candidate


def _base_journey(rich_repo: Path) -> Journey:
    return asyncio.run(JourneyPipeline().run(rich_repo, product_name="rich", source_commit="base"))


def test_llm_brancher_adds_milestone(rich_repo: Path):
    base = _base_journey(rich_repo)

    edits = {"summary": "add referral", "edits": [{
        "op": "add", "id": "referral_loop", "stage_id": "virality", "name": "Referral",
        "description": "referral flow", "evidence_paths": ["src/referral.ts"], "reason": "new"}]}
    llm = FakeLLM(complete_fn=lambda p, s: json.dumps(edits))

    journey = asyncio.run(LlmBrancher(llm).branch(
        base_journey=base, changed_paths={"src/referral.ts"}, removed_paths=set(),
        diff_text="+ referral", branch_worktree=rich_repo,
        product_name="rich", base_branch="main", source_commit="feat"))
    assert "virality" in {s.id for s in journey.stages}
    assert "via llm" in (journey.product.description or "").lower()


def test_llm_brancher_remove_all_yields_baseline(rich_repo: Path):
    """A branch that deletes the product → brancher removes every milestone → we still emit
    a valid (baseline) journey instead of raising 'no classified milestones'."""
    base = _base_journey(rich_repo)
    ids = [m.id for s in base.stages for m in s.milestones]
    assert ids  # sanity: the base has milestones to remove
    edits = {"summary": "removes everything", "edits": [{"op": "remove", "id": i} for i in ids]}
    llm = FakeLLM(complete_fn=lambda p, s: json.dumps(edits))

    journey = asyncio.run(LlmBrancher(llm).branch(
        base_journey=base, changed_paths=set(), removed_paths=set(ids),
        diff_text="- everything", branch_worktree=rich_repo,
        product_name="rich", base_branch="main", source_commit="feat"))

    assert isinstance(journey, Journey)
    all_ms = [m.id for st in journey.stages for m in st.milestones]
    assert all_ms == ["entry_point"]


def test_llm_brancher_empty_edits_equals_base(rich_repo: Path):
    base = _base_journey(rich_repo)
    llm = FakeLLM(complete_fn=lambda p, s: '{"summary": "", "edits": []}')
    journey = asyncio.run(LlmBrancher(llm).branch(
        base_journey=base, changed_paths={"README.md"}, removed_paths=set(),
        diff_text="", branch_worktree=rich_repo,
        product_name="rich", base_branch="main"))
    assert {s.id for s in journey.stages} == {s.id for s in base.stages}


class _RaisingBrancher:
    async def branch(self, **kwargs):
        raise RuntimeError("llm exploded")


def test_branch_from_propagates_brancher_error(rich_repo: Path):
    base = _base_journey(rich_repo)
    pipeline = JourneyPipeline(brancher=_RaisingBrancher())
    # With an LLM brancher configured, its errors propagate (no deterministic fallback).
    with pytest.raises(RuntimeError):
        asyncio.run(pipeline.branch_from(
            base, rich_repo, changed_paths=set(), removed_paths=set(),
            product_name="rich", base_branch="main", diff_text=""))


class _ErrLLM:
    async def complete(self, prompt: str, *, system: str | None = None) -> str:
        raise RuntimeError("provider down")

    async def chat(self, messages, tools=None):
        raise RuntimeError("provider down")


def test_run_is_marked_failed_on_llm_error(git_repo: Path, settings):
    """End-to-end: when the LLM step errors, the analysis run is recorded as failed."""
    async def run():
        # Heuristic extractor finds candidates (or a baseline); the LLM classify then errors.
        pipe = JourneyPipeline(classifier=LlmClassifier(_ErrLLM()))
        svc = DaemonService(settings, pipeline=pipe)
        await svc.start()
        try:
            project = await svc.add_project(str(git_repo))  # auto-analyzes default branch
            await svc.queue.join()
            runs = svc.list_runs(project.id)
            assert runs and runs[0].status == JobStatus.failed
            assert "llm" in (runs[0].error or "").lower()
        finally:
            await svc.stop()

    asyncio.run(run())


def test_factory_selects_backend():
    heuristic = build_pipeline(Settings(analysis_backend="auto", llm_model=None))
    assert type(heuristic.extractor).__name__ == "HeuristicCodeScanner"
    assert heuristic.brancher is None

    llm = build_pipeline(Settings(analysis_backend="llm", llm_model="test/model"))
    assert type(llm.extractor).__name__ == "LlmCodeAgent"
    assert type(llm.classifier).__name__ == "LlmClassifier"
    assert type(llm.brancher).__name__ == "LlmBrancher"
