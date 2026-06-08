"""Journey comparison — the engine behind gap analysis (branch vs gold) and drift
analysis (branch vs branch).

Pure functions over ``Journey`` objects. Milestones are aligned across the two journeys
(by id, then fuzzy name, then evidence-path overlap) and classified as:

- ``matched``  — present in both, unchanged
- ``changed``  — present in both, but its stage / evidence / tracked event moved
- ``missing``  — in the target but not the candidate
- ``added``    — in the candidate but not the target

For *gap*, target = gold standard, candidate = the branch ("what is this branch missing
vs the gold?"). For *drift*, target = base branch, candidate = head branch.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from .journey import Journey, Milestone

_TOKEN = re.compile(r"[^a-z0-9]+")


def _norm(name: str) -> str:
    return " ".join(sorted(t for t in _TOKEN.split(name.lower()) if t))


def _paths(m: Milestone) -> set[str]:
    return {ev.path for ev in m.evidence if ev.path}


class DeltaStatus(str, Enum):
    matched = "matched"
    changed = "changed"
    missing = "missing"
    added = "added"


class MilestoneDelta(BaseModel):
    status: DeltaStatus
    id: str
    name: str
    target_stage: str | None = None
    candidate_stage: str | None = None
    changes: list[str] = Field(default_factory=list)


class StageSummary(BaseModel):
    stage_id: str
    matched: int = 0
    changed: int = 0
    missing: int = 0
    added: int = 0


class ComparisonReport(BaseModel):
    kind: str                      # "gap" | "drift"
    target_label: str
    candidate_label: str
    coverage: float                # (matched + changed) / target milestone count
    matched: int
    changed: int
    missing: int
    added: int
    stages: list[StageSummary]
    deltas: list[MilestoneDelta]
    summary: str
    generated_at: datetime


def compare_journeys(
    target: Journey,
    candidate: Journey,
    *,
    kind: str,
    target_label: str,
    candidate_label: str,
    generated_at: datetime | None = None,
) -> ComparisonReport:
    generated_at = generated_at or datetime.now(timezone.utc)

    t_items = [(s.id, m) for s in target.stages for m in s.milestones]
    c_items = [(s.id, m) for s in candidate.stages for m in s.milestones]
    used = [False] * len(c_items)

    by_id: dict[str, int] = {}
    by_name: dict[str, int] = {}
    for i, (_, m) in enumerate(c_items):
        by_id.setdefault(m.id, i)
        by_name.setdefault(_norm(m.name), i)

    deltas: list[MilestoneDelta] = []
    for tsid, tm in t_items:
        j = _find_match(tm, by_id, by_name, c_items, used)
        if j is None:
            deltas.append(MilestoneDelta(status=DeltaStatus.missing, id=tm.id, name=tm.name, target_stage=tsid))
            continue
        used[j] = True
        csid, cm = c_items[j]
        changes = _changes(tsid, tm, csid, cm)
        deltas.append(MilestoneDelta(
            status=DeltaStatus.changed if changes else DeltaStatus.matched,
            id=tm.id, name=tm.name, target_stage=tsid, candidate_stage=csid, changes=changes,
        ))

    for i, (csid, cm) in enumerate(c_items):
        if not used[i]:
            deltas.append(MilestoneDelta(status=DeltaStatus.added, id=cm.id, name=cm.name, candidate_stage=csid))

    matched = sum(d.status == DeltaStatus.matched for d in deltas)
    changed = sum(d.status == DeltaStatus.changed for d in deltas)
    missing = sum(d.status == DeltaStatus.missing for d in deltas)
    added = sum(d.status == DeltaStatus.added for d in deltas)
    coverage = round((matched + changed) / len(t_items), 4) if t_items else 1.0

    summary = (
        f"{candidate_label} covers {matched + changed}/{len(t_items)} of {target_label} "
        f"({coverage:.0%}) — {missing} missing, {added} extra, {changed} changed."
    )
    return ComparisonReport(
        kind=kind,
        target_label=target_label,
        candidate_label=candidate_label,
        coverage=coverage,
        matched=matched, changed=changed, missing=missing, added=added,
        stages=_stage_summaries(deltas),
        deltas=deltas,
        summary=summary,
        generated_at=generated_at,
    )


def _find_match(tm: Milestone, by_id, by_name, c_items, used) -> int | None:
    for j in (by_id.get(tm.id), by_name.get(_norm(tm.name))):
        if j is not None and not used[j]:
            return j
    tp = _paths(tm)
    if tp:
        for i, (_, cm) in enumerate(c_items):
            if not used[i] and tp & _paths(cm):
                return i
    return None


def _changes(t_stage: str, tm: Milestone, c_stage: str, cm: Milestone) -> list[str]:
    out: list[str] = []
    if t_stage != c_stage:
        out.append(f"stage {t_stage} → {c_stage}")
    tp, cp = _paths(tm), _paths(cm)
    if cp - tp:
        out.append("evidence + " + ", ".join(sorted(cp - tp)))
    if tp - cp:
        out.append("evidence - " + ", ".join(sorted(tp - cp)))
    if (tm.tracked_event or None) != (cm.tracked_event or None):
        out.append(f"event {tm.tracked_event or '∅'} → {cm.tracked_event or '∅'}")
    return out


def _stage_summaries(deltas: list[MilestoneDelta]) -> list[StageSummary]:
    by_stage: dict[str, StageSummary] = {}

    def bucket(stage_id: str | None) -> StageSummary:
        sid = stage_id or "unknown"
        return by_stage.setdefault(sid, StageSummary(stage_id=sid))

    for d in deltas:
        if d.status == DeltaStatus.added:
            bucket(d.candidate_stage).added += 1
        elif d.status == DeltaStatus.missing:
            bucket(d.target_stage).missing += 1
        elif d.status == DeltaStatus.changed:
            bucket(d.target_stage).changed += 1
        else:
            bucket(d.target_stage).matched += 1
    return list(by_stage.values())
