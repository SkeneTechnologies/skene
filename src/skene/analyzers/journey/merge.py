"""Step 3 — merge of schema-side and code-side features.

:func:`merge_features_llm` is the entry point: one LLM call decides
which features describe the same capability (semantic duplicates the
old string matching missed, e.g. "Account Creation" vs "User signup"),
then each group is folded deterministically — evidence union, the
higher-confidence feature's name/description wins, confidences are
averaged. The result is the deduplicated *feature map*.

The rule-based :func:`merge_features` (exact ``proposed_id`` match,
then fuzzy name match) survives as the fallback when the LLM errors or
returns something that isn't a partition of the features.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ValidationError

from skene.analyzers._journey_common import parse_json
from skene.analyzers.journey.feature import Feature
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


def _merge_pair(a: Feature, b: Feature) -> Feature:
    primary, secondary = (a, b) if a.confidence >= b.confidence else (b, a)
    return Feature(
        proposed_id=primary.proposed_id,
        name=primary.name,
        description=primary.description,
        evidence=_union_evidence(primary.evidence, secondary.evidence),
        tracked_event=primary.tracked_event or secondary.tracked_event,
        # Average confidence — both sources seeing the same feature is a
        # boost, not a drop, but we don't want to blindly use the higher one.
        confidence=round((primary.confidence + secondary.confidence) / 2, 4),
    )


def _merge_group(group: list[Feature]) -> Feature:
    merged = group[0]
    for f in group[1:]:
        merged = _merge_pair(merged, f)
    return merged


class _MergeResult(BaseModel):
    groups: list[list[int]]


_MERGE_INSTRUCTIONS = """\
You deduplicate candidate product features. The features below were
gathered independently from a database schema and from source code, so
the same capability often appears more than once under different ids or
names.

Group features that describe the SAME capability. Judge by meaning, not
string similarity: "Account Creation" and "User signup" are the same
capability; "Invite Sent" and "Invite Accepted" are not.

Rules:
- Every feature index appears in exactly one group.
- A feature with no duplicate is a group of one.
- When genuinely unsure, keep features separate — a wrong merge loses a
  real feature, a missed merge only leaves a near-duplicate.

Return ONLY a JSON object with this exact shape, no prose, no markdown,
no code fences:
{"groups": [[0, 3], [1], [2]]}
"""


def _format_feature(idx: int, f: Feature) -> str:
    lines = [f"{idx}. id={f.proposed_id} name={f.name!r} — {f.description}"]
    if f.tracked_event:
        lines.append(f"   tracked_event: {f.tracked_event}")
    for ev in f.evidence:
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


async def merge_features_llm(
    schema_features: list[Feature],
    code_features: list[Feature],
    llm: LLMClient,
) -> list[Feature]:
    """Deduplicate the two streams with one LLM grouping call.

    Falls back to the rule-based :func:`merge_features` on LLM failure
    or an invalid grouping, so the pipeline never dies on this step.
    """
    features = [*schema_features, *code_features]
    if len(features) <= 1:
        return features

    prompt = _MERGE_INSTRUCTIONS + "\n\nFeatures:\n" + "\n".join(_format_feature(i, f) for i, f in enumerate(features))
    debug(f"merge LLM call → {len(features)} features")
    try:
        response = await llm.generate_content(prompt)
        groups = _parse_groups(response, len(features))
    except Exception as e:  # noqa: BLE001 — any failure falls back to the rule-based merge
        warning(f"merge agent failed ({e}); falling back to rule-based merge")
        return merge_features(schema_features, code_features)
    debug(f"merge LLM result ← {len(groups)} groups")
    return [_merge_group([features[i] for i in group]) for group in groups]


def merge_features(
    schema_features: list[Feature],
    code_features: list[Feature],
) -> list[Feature]:
    """Rule-based fallback: exact-id then fuzzy-name dedup of the two streams."""
    merged: list[Feature] = []
    by_id: dict[str, int] = {}
    by_norm_name: dict[str, int] = {}

    for f in [*schema_features, *code_features]:
        existing_idx: int | None = by_id.get(f.proposed_id)
        if existing_idx is None:
            existing_idx = by_norm_name.get(_normalize(f.name))
        if existing_idx is None:
            merged.append(f)
            idx = len(merged) - 1
            by_id[f.proposed_id] = idx
            by_norm_name[_normalize(f.name)] = idx
            continue

        combined = _merge_pair(merged[existing_idx], f)
        merged[existing_idx] = combined
        # Index under both ids/names in case they differed.
        by_id[f.proposed_id] = existing_idx
        by_id[combined.proposed_id] = existing_idx
        by_norm_name[_normalize(f.name)] = existing_idx
        by_norm_name[_normalize(combined.name)] = existing_idx
    return merged
