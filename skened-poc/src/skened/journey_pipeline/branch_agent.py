"""LLM brancher — derive a branch's journey from the default branch's journey + the diff.

The model is shown the BASE journey (the source branch's analysis) and the CODE DIFF, and
returns structured *edits* (add / update / remove milestones). We apply those edits to the
base deterministically and re-assemble, so the result is always a schema-valid Journey
regardless of what the model returns. On any failure the caller falls back to the
deterministic differ.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from ..journey import Evidence, EvidenceSource, Journey
from .assemble import assemble_journey
from .candidate import CandidateMilestone
from .classify import _parse_json
from .extract import _slugify
from .llm import LlmAnalysisError
from .stages import STAGE_IDS, stages_as_prompt

logger = logging.getLogger("skened.pipeline.branch_agent")

BRANCH_INSTRUCTIONS = """You maintain a product's user-journey map across git branches.

You are given the BASE journey (the previous analysis this branch builds on — either the
default branch, or this branch's own earlier analysis) and the CODE DIFF introduced since
that base. Decide how the journey changes:
- add a milestone for a NEW user-facing capability the diff introduces,
- update a milestone whose underlying code changed,
- remove a milestone whose code was deleted,
- leave everything else untouched (do NOT restate unchanged milestones).

Stages (use the id):
{stages}

Return ONLY a JSON object — no prose, no markdown, no code fences:
{{"summary": "<one line>", "edits": [
  {{"op": "add|update|remove", "id": "<milestone id, lowercase snake_case>",
    "stage_id": "<one of {ids}>", "name": "...", "description": "...",
    "evidence_paths": ["repo/relative/path"], "reason": "...",
    "tracked_event": "...", "confidence": 0.0}}
]}}
For "remove" only "op" and "id" are needed. For "add" include stage_id and at least one
evidence_path. If the diff does not change the journey, return an empty edits list.
"""


class MilestoneEdit(BaseModel):
    op: Literal["add", "update", "remove"]
    id: str
    stage_id: str | None = None
    name: str | None = None
    description: str | None = None
    evidence_paths: list[str] | None = None
    reason: str | None = None
    tracked_event: str | None = None
    confidence: float | None = None


class BranchEdits(BaseModel):
    summary: str = ""
    edits: list[MilestoneEdit] = []


class LlmBrancher:
    def __init__(self, llm) -> None:
        self._llm = llm
        self._instructions = BRANCH_INSTRUCTIONS.format(
            stages=stages_as_prompt(), ids=sorted(STAGE_IDS)
        )

    async def branch(
        self,
        *,
        base_journey: Journey,
        changed_paths: set[str],
        removed_paths: set[str],
        diff_text: str,
        branch_worktree: Path,
        product_name: str,
        base_branch: str,
        source_commit: str | None = None,
        generated_at: datetime | None = None,
    ) -> Journey:
        # Local import avoids a circular import at module load (pipeline references a Brancher).
        from .pipeline import _baseline_candidate, candidates_from_journey

        base = candidates_from_journey(base_journey)
        prompt = _build_prompt(base, diff_text, removed_paths)
        try:
            raw = await self._llm.complete(prompt, system=self._instructions)
            edits = BranchEdits.model_validate(_parse_json(raw))
        except Exception as e:  # noqa: BLE001 — fail the run instead of degrading to the differ
            raise LlmAnalysisError(f"LLM brancher failed: {e}") from e
        logger.info("LLM brancher: %d edit(s) — %s", len(edits.edits), edits.summary)

        candidates = _apply_edits(base, edits)
        if not candidates:
            candidates = [_baseline_candidate(branch_worktree)]

        desc = f"Branched from '{base_branch}' via LLM — {edits.summary or 'no journey changes'}."
        return assemble_journey(
            candidates, product_name,
            generated_at=generated_at, source_commit=source_commit, product_description=desc,
        )


def _build_prompt(base: list[CandidateMilestone], diff_text: str, removed_paths: set[str]) -> str:
    lines = ["BASE journey milestones (id | stage | name | evidence):"]
    for c in base:
        paths = ", ".join(ev.path or ev.table or "?" for ev in c.evidence)
        lines.append(f"- {c.proposed_id} | {c.stage_id} | {c.name} | {paths}")
    lines.append("\nREMOVED files: " + (", ".join(sorted(removed_paths)) or "(none)"))
    lines.append("\nCODE DIFF:\n" + (diff_text or "(empty)"))
    return "\n".join(lines)


def _apply_edits(base: list[CandidateMilestone], edits: BranchEdits) -> list[CandidateMilestone]:
    by_id: dict[str, CandidateMilestone] = {c.proposed_id: c for c in base}

    for e in edits.edits:
        if e.op == "remove":
            by_id.pop(e.id, None)

        elif e.op == "update":
            cur = by_id.get(e.id)
            if cur is None:
                continue
            updates: dict = {}
            if e.name:
                updates["name"] = e.name
            if e.description:
                updates["description"] = e.description
            if e.stage_id in STAGE_IDS:
                updates["stage_id"] = e.stage_id
            if e.tracked_event is not None:
                updates["tracked_event"] = e.tracked_event
            if e.confidence is not None:
                updates["confidence"] = max(0.0, min(1.0, e.confidence))
            if e.evidence_paths:
                updates["evidence"] = _evidence(e.evidence_paths, e.reason)
            by_id[e.id] = cur.model_copy(update=updates)

        elif e.op == "add":
            evidence = _evidence(e.evidence_paths or [], e.reason)
            if not evidence:
                logger.debug("skipping add %r with no evidence path", e.id)
                continue
            mid = _slugify(e.id)
            name = e.name or mid
            by_id[mid] = CandidateMilestone(
                proposed_id=mid,
                name=name,
                description=e.description or name,
                evidence=evidence,
                tracked_event=e.tracked_event,
                confidence=max(0.0, min(1.0, e.confidence if e.confidence is not None else 0.6)),
                stage_id=e.stage_id if e.stage_id in STAGE_IDS else "engagement",
            )

    return list(by_id.values())


def _evidence(paths: list[str], reason: str | None) -> list[Evidence]:
    r = reason or "Introduced/changed by branch."
    return [Evidence(source=EvidenceSource.code, path=p, reason=r) for p in paths if p]
