"""Group classified candidates by stage and build a validated Journey.

Ported from analyze-journey. Drops unclassified candidates, sorts each stage bucket by
``proposed_id`` for deterministic order, resolves intra-stage ID collisions by appending
``_2``/``_3``, and assembles the standard 4-layer swimlane model. Round-trip validates;
raises ``ValueError`` on an empty journey rather than emitting garbage.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..journey import Evidence, Journey, Layer, Milestone, Product, Stage
from .candidate import CandidateMilestone
from .stages import DEFAULT_LAYERS, STAGES, StageDef

logger = logging.getLogger("skened.pipeline.assemble")


def assemble_journey(
    candidates: list[CandidateMilestone],
    product_name: str,
    *,
    generated_at: datetime | None = None,
    source_commit: str | None = None,
    product_description: str | None = None,
    stages: tuple[StageDef, ...] = STAGES,
) -> Journey:
    if generated_at is None:
        generated_at = datetime.now(timezone.utc)

    by_stage: dict[str, list[CandidateMilestone]] = {}
    for cm in candidates:
        if cm.stage_id is None:
            logger.debug("dropping unclassified candidate %s", cm.proposed_id)
            continue
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
        raise ValueError("no classified milestones — refusing to emit an empty journey")

    present = {s.id for s in out_stages}
    layers: list[Layer] = []
    for lid, lname, spans in DEFAULT_LAYERS:
        spanned = [s for s in spans if s in present]
        if spanned:
            layers.append(Layer(id=lid, name=lname, spans_stages=spanned))

    journey = Journey(
        product=Product(
            name=product_name,
            description=product_description,
            generated_at=generated_at,
            source_commit=source_commit,
        ),
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
