"""Step 4 — milestone synthesis from the merged feature map.

:func:`synthesize_milestones_llm` is the step the whole restructure
exists for: one LLM call that sees the *entire* deduplicated feature map
plus the (possibly specialized) stage definitions, and composes actual
product milestones from it — many features fold into one milestone,
named from the user's perspective ("First estimate generated", not
"estimates table exists"), each assigned a journey stage. Milestone
evidence is the union of its member features' evidence, so journey.yaml
keeps full traceability back to code paths and DB tables.

Because the model sees every feature at once, stage assignment happens
here too, with global context. The per-feature classifier
(:mod:`skene.analyzers.journey.classify`) survives as the fallback: on
LLM failure or an invalid grouping, every feature becomes its own
candidate milestone and is classified in isolation — exactly the
pre-synthesis behavior.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, ValidationError

from skene.analyzers._journey_common import parse_json
from skene.analyzers.journey.candidate import CandidateMilestone
from skene.analyzers.journey.classify import classify_all
from skene.analyzers.journey.feature import Feature
from skene.analyzers.journey.models import Evidence
from skene.analyzers.journey.stages import STAGE_IDS, STAGES, StageDef, stages_as_prompt
from skene.llm.base import LLMClient
from skene.output import debug, status, warning
from skene.schema.feature import ID_PATTERN


class _SynthesizedMilestone(BaseModel):
    proposed_id: str = Field(pattern=ID_PATTERN)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    stage_id: str
    features: list[int] = Field(min_length=1)
    tracked_event: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class _SynthesisResult(BaseModel):
    milestones: list[_SynthesizedMilestone] = Field(min_length=1)


_SYNTHESIZE_INSTRUCTIONS_TEMPLATE = """\
You synthesize product milestones from a feature map. The features below
were gathered from the product's source code and database schema; each
one is a capability with evidence. Your job is to compose the actual
user journey from them: group related features into milestones — steps a
user passes through — and assign each milestone to a journey stage.

Stages:
{stages}

Coverage honesty — the most important rule:
- The analysed sources usually cover only PART of the journey. A
  product's discovery may live on a separate marketing website,
  retention in a CRM, virality in an ads platform — none of which you
  can see here.
- Populate a stage ONLY when the evidence genuinely shows that lifecycle
  step implemented in the analysed system. Leaving a stage completely
  empty is correct and expected — an honest partial journey beats a
  padded complete-looking one.
- Never stretch or promote a feature into a stage to fill the funnel.
  Example: an in-app signup/login flow is the START of onboarding, not
  discovery — discovery needs real acquisition surfaces (landing pages,
  pricing pages, campaign attribution) in the evidence.

How to compose milestones:
- A milestone is a meaningful step in the user's life with the product,
  named from the USER'S perspective ("First estimate generated", not
  "estimates table"). Several features usually support one milestone —
  fold them together. A single strong feature can also stand alone.
- Do not force unrelated features into one milestone: group only
  features that a user would experience as the same step.
- Order matters within the journey; put each milestone in the stage
  where the user hits it. Apply these signals in order — the first
  matching signal wins:
  1. Monetization (payment, billing, checkout, subscription, upgrade,
     seats, paid features) → 'expansion', even if it could also fit
     activation or onboarding.
  2. Virality (referrals, invites outside the workspace, share links,
     public pages, attribution) → 'virality'.
  3. First real value (the product's primary output delivered for the
     first time) → 'activation'.
  4. Ambiguity between adjacent lifecycle stages → the earlier stage.
- A noisy feature that does not represent anything a user experiences
  (internal bookkeeping, framework plumbing) may be left out of every
  milestone.
- Set confidence < 0.7 when a milestone's grouping or stage is a guess.
- Use lowercase snake_case for proposed_id; ids must be unique.
- tracked_event: if one of the grouped features has a strong analytics
  event name, carry it; otherwise omit it.

Return ONLY a JSON object with this exact shape, no prose, no markdown,
no code fences:
{{"milestones": [
  {{"proposed_id": "first_estimate_generated",
    "name": "First Estimate Generated",
    "description": "<1-2 sentences, user perspective>",
    "stage_id": "<one of {ids}>",
    "features": [0, 3, 7],
    "tracked_event": "estimate_created",
    "confidence": 0.9}}
]}}

`features` lists the indices of the features that make up the milestone.
Every index must exist and no index may appear in two milestones.
"""


def _build_instructions(stages: tuple[StageDef, ...]) -> str:
    return _SYNTHESIZE_INSTRUCTIONS_TEMPLATE.format(stages=stages_as_prompt(stages), ids=sorted(STAGE_IDS))


def _format_feature(idx: int, f: Feature) -> str:
    lines = [f"{idx}. id={f.proposed_id} name={f.name!r} — {f.description}"]
    if f.tracked_event:
        lines.append(f"   tracked_event: {f.tracked_event}")
    for ev in f.evidence:
        loc = ev.path or ev.table or "?"
        lines.append(f"   evidence {ev.source.value}: {loc} — {ev.reason}")
    return "\n".join(lines)


def _union_evidence(groups: list[list[Evidence]]) -> list[Evidence]:
    seen: set[tuple] = set()
    out: list[Evidence] = []
    for evidence in groups:
        for ev in evidence:
            key = (ev.source, ev.path, ev.table, ev.reason)
            if key in seen:
                continue
            seen.add(key)
            out.append(ev)
    return out


def _parse_result(response: str, count: int) -> _SynthesisResult:
    """Validated synthesis result; raises unless indices are sane."""
    parsed = parse_json(response)
    if parsed is None:
        raise ValueError(f"synthesis agent returned non-JSON response: {response[:200]!r}")
    try:
        result = _SynthesisResult.model_validate(parsed)
    except ValidationError as e:
        raise ValueError(f"synthesis agent returned invalid result: {e}") from e

    seen: set[int] = set()
    for m in result.milestones:
        for idx in m.features:
            if not 0 <= idx < count:
                raise ValueError(f"synthesis milestone {m.proposed_id!r} references unknown feature index {idx}")
            if idx in seen:
                raise ValueError(f"feature index {idx} appears in more than one synthesized milestone")
            seen.add(idx)
        if m.stage_id not in STAGE_IDS:
            raise ValueError(f"synthesis milestone {m.proposed_id!r} has unknown stage_id {m.stage_id!r}")
    return result


def _fold(m: _SynthesizedMilestone, features: list[Feature]) -> CandidateMilestone:
    members = [features[i] for i in m.features]
    member_confidence = sum(f.confidence for f in members) / len(members)
    return CandidateMilestone(
        proposed_id=m.proposed_id,
        name=m.name,
        description=m.description,
        evidence=_union_evidence([f.evidence for f in members]),
        tracked_event=m.tracked_event or next((f.tracked_event for f in members if f.tracked_event), None),
        confidence=round(min(m.confidence, member_confidence), 4),
        stage_id=m.stage_id,
    )


async def synthesize_milestones_llm(
    features: list[Feature],
    llm: LLMClient,
    *,
    stages: tuple[StageDef, ...] | None = None,
    classify_concurrency: int = 8,
    sources: str | None = None,
) -> list[CandidateMilestone]:
    """Compose candidate milestones from the feature map with one LLM call.

    ``sources`` is a human-readable description of the evidence sources
    that were analysed (repo path, schema dir / live DB, ...). It lets
    the model judge which journey stages this analysis can actually see,
    so stages outside that coverage stay empty instead of being padded.

    Falls back to per-feature classification (every feature its own
    milestone — the pre-synthesis behavior) on LLM failure or an invalid
    grouping, so the pipeline never dies on this step.
    """
    effective_stages = stages if stages is not None else STAGES
    sources_block = (
        f"\n\nEvidence sources analysed (the journey outside them is invisible to this analysis):\n{sources}"
        if sources
        else ""
    )
    prompt = (
        _build_instructions(effective_stages)
        + sources_block
        + "\n\nFeatures:\n"
        + "\n".join(_format_feature(i, f) for i, f in enumerate(features))
    )
    debug(f"synthesize LLM call → {len(features)} features")
    try:
        response = await llm.generate_content(prompt)
        result = _parse_result(response, len(features))
        candidates = [_fold(m, features) for m in result.milestones]
    except Exception as e:  # noqa: BLE001 — any failure falls back to 1:1 classification
        warning(f"synthesis agent failed ({e}); falling back to per-feature classification")
        return await classify_all(features, llm, concurrency=classify_concurrency, stages=stages)

    used = sum(len(m.features) for m in result.milestones)
    if used < len(features):
        dropped = [f.proposed_id for i, f in enumerate(features) if not any(i in m.features for m in result.milestones)]
        status(f"synthesize: {len(dropped)} feature(s) left out of every milestone: {', '.join(dropped)}")
    debug(f"synthesize LLM result ← {len(candidates)} milestones from {used}/{len(features)} features")
    return candidates
