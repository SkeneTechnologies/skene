"""Tests for the merge step (Step 3): LLM grouping + rule-based fallback."""

from __future__ import annotations

import json
from typing import AsyncGenerator

import pytest

from skene.analyzers.journey.candidate import CandidateMilestone
from skene.analyzers.journey.merge import merge_candidates, merge_candidates_llm
from skene.analyzers.journey.models import Evidence
from skene.llm.base import LLMClient


class _MergeFake(LLMClient):
    """Answers every ``generate_content`` call with one canned response."""

    def __init__(self, response: str) -> None:
        self._response = response
        self.prompts: list[str] = []

    async def generate_content_with_usage(self, prompt: str) -> tuple[str, dict[str, int] | None]:
        self.prompts.append(prompt)
        return self._response, None

    async def generate_content_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        if False:
            yield ""
        raise NotImplementedError

    def get_model_name(self) -> str:
        return "merge-fake"

    def get_provider_name(self) -> str:
        return "fake"


def _code(pid: str, name: str, path: str, confidence: float = 0.8) -> CandidateMilestone:
    return CandidateMilestone(
        proposed_id=pid,
        name=name,
        description=name,
        evidence=[Evidence(source="code", path=path, reason="found")],
        confidence=confidence,
    )


def _db(pid: str, name: str, table: str, confidence: float = 0.8) -> CandidateMilestone:
    return CandidateMilestone(
        proposed_id=pid,
        name=name,
        description=name,
        evidence=[Evidence(source="db", table=table, reason="row")],
        confidence=confidence,
    )


def test_exact_id_match_merges_evidence():
    schema = [_db("account_created", "Account Created", "users", 0.9)]
    code = [_code("account_created", "Account Created", "src/api/signup.ts", 0.8)]
    out = merge_candidates(schema, code)
    assert len(out) == 1
    sources = {ev.source.value for ev in out[0].evidence}
    assert sources == {"db", "code"}


def test_fuzzy_name_match_merges():
    schema = [_db("acct_created", "Account  Created!", "users")]
    code = [_code("account_created", "account created", "src/api/signup.ts")]
    out = merge_candidates(schema, code)
    assert len(out) == 1
    assert len(out[0].evidence) == 2


def test_no_match_keeps_both():
    schema = [_db("account_created", "Account Created", "users")]
    code = [_code("landing_view", "Landing Page View", "src/pages/index.tsx")]
    out = merge_candidates(schema, code)
    assert len(out) == 2
    ids = {cm.proposed_id for cm in out}
    assert ids == {"account_created", "landing_view"}


def test_higher_confidence_wins_name():
    schema = [_db("a", "Signup Completed", "users", confidence=0.6)]
    code = [_code("a", "Account Created", "src/api/signup.ts", confidence=0.95)]
    out = merge_candidates(schema, code)
    assert len(out) == 1
    assert out[0].name == "Account Created"


async def test_llm_merge_groups_semantic_duplicates():
    schema = [_db("account_created", "Account Created", "users", 0.9)]
    code = [
        _code("user_signs_up", "User signs up", "src/api/signup.ts", 0.8),
        _code("landing_view", "Landing Page View", "src/pages/index.tsx"),
    ]
    llm = _MergeFake(json.dumps({"groups": [[0, 1], [2]]}))
    out = await merge_candidates_llm(schema, code, llm)
    assert len(out) == 2
    merged = out[0]
    # Higher-confidence candidate wins the identity; evidence is unioned.
    assert merged.proposed_id == "account_created"
    assert {ev.source.value for ev in merged.evidence} == {"db", "code"}
    assert merged.confidence == pytest.approx(0.85)
    assert out[1].proposed_id == "landing_view"


async def test_llm_merge_single_candidate_skips_llm():
    llm = _MergeFake("should never be called")
    out = await merge_candidates_llm([_db("a", "A", "users")], [], llm)
    assert len(out) == 1
    assert llm.prompts == []


async def test_llm_merge_falls_back_on_non_json():
    schema = [_db("account_created", "Account Created", "users")]
    code = [_code("account_created", "Account Created", "src/api/signup.ts")]
    out = await merge_candidates_llm(schema, code, _MergeFake("no json here"))
    # Rule-based fallback still merges the exact-id duplicate.
    assert len(out) == 1
    assert {ev.source.value for ev in out[0].evidence} == {"db", "code"}


async def test_llm_merge_falls_back_on_bad_partition():
    schema = [_db("account_created", "Account Created", "users")]
    code = [_code("landing_view", "Landing Page View", "src/pages/index.tsx")]
    # Index 1 missing, index 5 out of range.
    out = await merge_candidates_llm(schema, code, _MergeFake(json.dumps({"groups": [[0, 5]]})))
    assert {cm.proposed_id for cm in out} == {"account_created", "landing_view"}


async def test_llm_merge_falls_back_on_llm_error():
    class _Boom(_MergeFake):
        async def generate_content_with_usage(self, prompt: str) -> tuple[str, dict[str, int] | None]:
            raise RuntimeError("provider down")

    schema = [_db("account_created", "Account Created", "users")]
    code = [_code("account_created", "Account Created", "src/api/signup.ts")]
    out = await merge_candidates_llm(schema, code, _Boom(""))
    assert len(out) == 1


def test_evidence_deduplicates_within_merge():
    e = Evidence(source="code", path="src/api/signup.ts", reason="found")
    a = CandidateMilestone(
        proposed_id="x",
        name="X",
        description="X",
        evidence=[e],
        confidence=0.8,
    )
    b = CandidateMilestone(
        proposed_id="x",
        name="X",
        description="X",
        evidence=[e],
        confidence=0.8,
    )
    out = merge_candidates([a], [b])
    assert len(out) == 1
    assert len(out[0].evidence) == 1
