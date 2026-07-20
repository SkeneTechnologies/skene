"""Step 5 — group synthesized candidates by stage and build a validated Journey.

Pure function (no LLM). Sorts each stage bucket alphabetically by
``proposed_id`` for deterministic order, resolves ID collisions within a
stage by appending ``_2``, ``_3``, ..., and assembles layers using the
standard 4-layer swim-lane model.

If the resulting Journey fails Pydantic validation, this raises — we do
not patch around malformed output. The caller surfaces the error so the
user can re-run.
"""

from __future__ import annotations

from datetime import datetime, timezone

from skene.analyzers.journey.candidate import CandidateMilestone
from skene.analyzers.journey.models import (
    Evidence,
    Journey,
    Layer,
    Milestone,
    Product,
    Stage,
)
from skene.analyzers.journey.stages import STAGES, StageDef

# Standard 4-layer model: a coarse grouping of the seven stages used for
# the "swimlane" view in the rendered journey map.
_DEFAULT_LAYERS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("L1", "Acquisition", ("discovery",)),
    ("L2", "Onboarding & Activation", ("onboarding", "activation")),
    ("L3", "Engagement & Retention", ("engagement", "retention")),
    ("L4", "Growth", ("expansion", "virality")),
)


def assemble_journey(
    candidates: list[CandidateMilestone],
    product_name: str,
    generated_at: datetime | None = None,
    stages: tuple[StageDef, ...] = STAGES,
) -> Journey:
    """Group candidates by stage, build the Journey, validate it."""
    if generated_at is None:
        generated_at = datetime.now(timezone.utc)

    by_stage: dict[str, list[CandidateMilestone]] = {}
    for cm in candidates:
        by_stage.setdefault(cm.stage_id, []).append(cm)

    out_stages: list[Stage] = []
    for stage_def in stages:
        bucket = by_stage.get(stage_def.id)
        if not bucket:
            continue
        bucket_sorted = sorted(bucket, key=lambda c: c.proposed_id)
        milestones: list[Milestone] = []
        used_ids: set[str] = set()
        for order, cm in enumerate(bucket_sorted, start=1):
            final_id = _unique_id(cm.proposed_id, used_ids)
            used_ids.add(final_id)
            milestones.append(_to_milestone(cm, final_id=final_id, order=order))
        out_stages.append(
            Stage(
                id=stage_def.id,
                order=stage_def.order,
                name=stage_def.name,
                subtitle=stage_def.subtitle,
                milestones=milestones,
                kpis=[],
            )
        )

    if not out_stages:
        raise ValueError("no synthesized milestones — refusing to emit an empty journey")

    present_stage_ids = {s.id for s in out_stages}
    layers: list[Layer] = []
    for lid, lname, spans in _DEFAULT_LAYERS:
        present = [s for s in spans if s in present_stage_ids]
        if present:
            layers.append(Layer(id=lid, name=lname, spans_stages=present))

    journey = Journey(
        product=Product(name=product_name, generated_at=generated_at),
        layers=layers,
        stages=out_stages,
        connectors=[],
    )
    # Round-trip validate to catch anything the models let slip.
    return Journey.model_validate(journey.model_dump(by_alias=True))


def _unique_id(proposed: str, used: set[str]) -> str:
    if proposed not in used:
        return proposed
    i = 2
    while f"{proposed}_{i}" in used:
        i += 1
    return f"{proposed}_{i}"


def _to_milestone(cm: CandidateMilestone, final_id: str, order: int) -> Milestone:
    return Milestone(
        id=final_id,
        order=order,
        name=cm.name,
        description=cm.description,
        evidence=_dedup_evidence(cm.evidence),
        tracked_event=cm.tracked_event,
        confidence=cm.confidence,
    )


def _dedup_evidence(evidence: list[Evidence]) -> list[Evidence]:
    seen: set[tuple] = set()
    out: list[Evidence] = []
    for ev in evidence:
        key = (ev.source, ev.path, ev.table, ev.reason)
        if key in seen:
            continue
        seen.add(key)
        out.append(ev)
    return out
