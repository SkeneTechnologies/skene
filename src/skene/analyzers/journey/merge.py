"""Step 3 — merge of schema-side and code-side candidates.

:func:`merge_candidates_llm` is the entry point: one LLM call decides
which candidates describe the same user action (semantic duplicates the
old string matching missed, e.g. "Account Created" vs "User signs up"),
then each group is folded deterministically — evidence union, the
higher-confidence candidate's name/description wins, confidences are
averaged.

The rule-based :func:`merge_candidates` (exact ``proposed_id`` match,
then fuzzy name match) survives as the fallback when the LLM errors or
returns something that isn't a partition of the candidates.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ValidationError

from skene.analyzers._journey_common import parse_json
from skene.analyzers.journey.candidate import CandidateMilestone
from skene.analyzers.journey.models import Evidence
from skene.llm.base import LLMClient
from skene.output import debug, warning

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
        # Average confidence — both sources seeing the same milestone is a
        # boost, not a drop, but we don't want to blindly use the higher one.
        confidence=round((primary.confidence + secondary.confidence) / 2, 4),
        stage_id=primary.stage_id or secondary.stage_id,
    )


def _merge_group(group: list[CandidateMilestone]) -> CandidateMilestone:
    merged = group[0]
    for cm in group[1:]:
        merged = _merge_pair(merged, cm)
    return merged


class _MergeResult(BaseModel):
    groups: list[list[int]]


_MERGE_INSTRUCTIONS = """\
You deduplicate candidate user-journey milestones. The candidates below
were gathered independently from a database schema and from source code,
so the same user action often appears more than once under different ids
or names.

Group candidates that describe the SAME user action. Judge by meaning,
not string similarity: "Account Created" and "User signs up" are the
same action; "Invite Sent" and "Invite Accepted" are not.

Rules:
- Every candidate index appears in exactly one group.
- A candidate with no duplicate is a group of one.
- When genuinely unsure, keep candidates separate — a wrong merge loses
  a real milestone, a missed merge only leaves a near-duplicate.

Return ONLY a JSON object with this exact shape, no prose, no markdown,
no code fences:
{"groups": [[0, 3], [1], [2]]}
"""


def _format_candidate(idx: int, cm: CandidateMilestone) -> str:
    lines = [f"{idx}. id={cm.proposed_id} name={cm.name!r} — {cm.description}"]
    if cm.tracked_event:
        lines.append(f"   tracked_event: {cm.tracked_event}")
    for ev in cm.evidence:
        loc = ev.path or ev.table or "?"
        lines.append(f"   evidence {ev.source.value}: {loc} — {ev.reason}")
    return "\n".join(lines)


def _parse_groups(response: str, count: int) -> list[list[int]]:
    """Validated groups from the LLM response; raises unless a partition."""
    parsed = parse_json(response)
    if parsed is None:
        raise ValueError(f"merge agent returned non-JSON response: {response[:200]!r}")
    try:
        result = _MergeResult.model_validate(parsed)
    except ValidationError as e:
        raise ValueError(f"merge agent returned invalid result: {e}") from e
    flat = [i for group in result.groups for i in group]
    if sorted(flat) != list(range(count)):
        raise ValueError(f"merge agent groups are not a partition of 0..{count - 1}: {result.groups}")
    return result.groups


async def merge_candidates_llm(
    schema_candidates: list[CandidateMilestone],
    code_candidates: list[CandidateMilestone],
    llm: LLMClient,
) -> list[CandidateMilestone]:
    """Deduplicate the two streams with one LLM grouping call.

    Falls back to the rule-based :func:`merge_candidates` on LLM failure
    or an invalid grouping, so finalize never dies on this step.
    """
    candidates = [*schema_candidates, *code_candidates]
    if len(candidates) <= 1:
        return candidates

    prompt = _MERGE_INSTRUCTIONS + "\n\nCandidates:\n" + "\n".join(
        _format_candidate(i, cm) for i, cm in enumerate(candidates)
    )
    debug(f"merge LLM call → {len(candidates)} candidates")
    try:
        response = await llm.generate_content(prompt)
        groups = _parse_groups(response, len(candidates))
    except Exception as e:  # noqa: BLE001 — any failure falls back to the rule-based merge
        warning(f"merge agent failed ({e}); falling back to rule-based merge")
        return merge_candidates(schema_candidates, code_candidates)
    debug(f"merge LLM result ← {len(groups)} groups")
    return [_merge_group([candidates[i] for i in group]) for group in groups]


def merge_candidates(
    schema_candidates: list[CandidateMilestone],
    code_candidates: list[CandidateMilestone],
) -> list[CandidateMilestone]:
    """Rule-based fallback: exact-id then fuzzy-name dedup of the two streams."""
    merged: list[CandidateMilestone] = []
    by_id: dict[str, int] = {}
    by_norm_name: dict[str, int] = {}

    for cm in [*schema_candidates, *code_candidates]:
        existing_idx: int | None = by_id.get(cm.proposed_id)
        if existing_idx is None:
            existing_idx = by_norm_name.get(_normalize(cm.name))
        if existing_idx is None:
            merged.append(cm)
            idx = len(merged) - 1
            by_id[cm.proposed_id] = idx
            by_norm_name[_normalize(cm.name)] = idx
            continue

        combined = _merge_pair(merged[existing_idx], cm)
        merged[existing_idx] = combined
        # Index under both ids/names in case they differed.
        by_id[cm.proposed_id] = existing_idx
        by_id[combined.proposed_id] = existing_idx
        by_norm_name[_normalize(cm.name)] = existing_idx
        by_norm_name[_normalize(combined.name)] = existing_idx
    return merged
