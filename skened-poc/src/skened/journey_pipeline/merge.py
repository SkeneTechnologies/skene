"""Deterministic merge of candidate milestones (ported from analyze-journey).

No LLM. Rules, in order:
1. Exact ``proposed_id`` match → merge (evidence unioned, higher-confidence name/desc wins).
2. Fuzzy name match (lowercase, strip punctuation, sort tokens) → merge.
3. Otherwise keep both.
"""

from __future__ import annotations

import re

from ..journey import Evidence
from .candidate import CandidateMilestone

_TOKEN_SPLIT = re.compile(r"[^a-z0-9]+")


def _normalize(name: str) -> str:
    tokens = sorted(t for t in _TOKEN_SPLIT.split(name.lower()) if t)
    return " ".join(tokens)


def _union_evidence(a: list[Evidence], b: list[Evidence]) -> list[Evidence]:
    seen: set[tuple] = set()
    out: list[Evidence] = []
    for ev in [*a, *b]:
        key = (ev.source, ev.path, ev.table, ev.reason)
        if key in seen:
            continue
        seen.add(key)
        out.append(ev)
    return out


def _merge_pair(a: CandidateMilestone, b: CandidateMilestone) -> CandidateMilestone:
    primary, secondary = (a, b) if a.confidence >= b.confidence else (b, a)
    return CandidateMilestone(
        proposed_id=primary.proposed_id,
        name=primary.name,
        description=primary.description,
        evidence=_union_evidence(primary.evidence, secondary.evidence),
        tracked_event=primary.tracked_event or secondary.tracked_event,
        confidence=round((primary.confidence + secondary.confidence) / 2, 4),
        stage_id=primary.stage_id or secondary.stage_id,
    )


def merge_candidates(*streams: list[CandidateMilestone]) -> list[CandidateMilestone]:
    """Deduplicate one or more candidate streams into a single list."""
    merged: list[CandidateMilestone] = []
    by_id: dict[str, int] = {}
    by_norm_name: dict[str, int] = {}

    for cm in (cm for stream in streams for cm in stream):
        idx = by_id.get(cm.proposed_id)
        if idx is None:
            idx = by_norm_name.get(_normalize(cm.name))
        if idx is None:
            merged.append(cm)
            new_idx = len(merged) - 1
            by_id[cm.proposed_id] = new_idx
            by_norm_name[_normalize(cm.name)] = new_idx
            continue

        combined = _merge_pair(merged[idx], cm)
        merged[idx] = combined
        by_id[cm.proposed_id] = idx
        by_id[combined.proposed_id] = idx
        by_norm_name[_normalize(cm.name)] = idx
        by_norm_name[_normalize(combined.name)] = idx
    return merged
