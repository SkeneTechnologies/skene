"""Step 4 — per-milestone stage classification.

One LLM call per candidate, no tools, structured JSON output parsed with
:func:`skene.analyzers._journey_common.parse_json`. Runs in parallel
with a semaphore.

We use the plain text-in/text-out :meth:`LLMClient.generate_content` rather
than the tool-use API: the model has nothing to call, it just needs to
return one JSON object with a stage assignment. That keeps this step
provider-agnostic on day one — every supported provider has
``generate_content`` working.
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field, ValidationError

from skene.analyzers._journey_common import parse_json
from skene.analyzers.journey.candidate import CandidateMilestone
from skene.analyzers.journey.stages import STAGE_IDS, STAGES, StageDef, stages_as_prompt
from skene.llm.base import LLMClient
from skene.output import debug, warning


class ClassificationResult(BaseModel):
    stage_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


_INSTRUCTIONS_TEMPLATE = """\
You classify a single user-journey milestone into one of seven stages.

Stages:
{stages}

Rules, applied in order — the first matching rule wins:

1. Monetization signal → 'expansion'. If the milestone involves payment,
   billing, checkout, subscription, plan upgrade, seat addition, paid
   feature unlock, usage overage, or anything that increases account
   value, classify it as 'expansion' even if it could also fit
   activation or onboarding. Examples: checkout sessions, Stripe
   webhooks, plan changes, paid-only API access, premium-feature
   enablement.

2. Virality signal → 'virality'. If the milestone involves referrals,
   invites sent to people outside the workspace, share links, public
   pages, attribution, embeds with attribution, or anything where one
   user brings in others, classify it as 'virality' — never push these
   to engagement or activation.

3. First real value → 'activation'. If the milestone is the user
   receiving the product's primary output for the first time (an
   estimate generated, a lead received, a chat answered), prefer
   'activation'.

4. Lifecycle ambiguity → earlier in the funnel. If a milestone fits two
   *adjacent lifecycle* stages (discovery vs onboarding, onboarding vs
   activation, engagement vs retention), prefer the earlier. This rule
   does NOT apply to expansion or virality — those are handled above.

5. Set confidence < 0.7 when genuinely ambiguous.

Return ONLY a JSON object with this exact shape, no prose, no markdown,
no code fences:
{{"stage_id": "<one of {ids}>", "confidence": <0.0..1.0>, "reason": "<short>"}}
"""


def _build_instructions(stages: tuple[StageDef, ...] = STAGES) -> str:
    return _INSTRUCTIONS_TEMPLATE.format(
        stages=stages_as_prompt(stages), ids=sorted(STAGE_IDS)
    )


def _format_input(cm: CandidateMilestone) -> str:
    evidence_lines = []
    for ev in cm.evidence:
        loc = ev.path or ev.table or "?"
        evidence_lines.append(f"- {ev.source.value}: {loc} — {ev.reason}")
    return (
        f"Milestone: {cm.name}\n"
        f"Description: {cm.description}\n"
        f"Tracked event: {cm.tracked_event or '(none)'}\n"
        f"Evidence:\n" + "\n".join(evidence_lines)
    )


async def classify_milestone(
    cm: CandidateMilestone,
    llm: LLMClient,
    stages: tuple[StageDef, ...] | None = None,
) -> ClassificationResult:
    """Classify a single milestone. Raises on LLM failure or invalid output."""
    effective_stages = stages if stages is not None else STAGES
    prompt = _build_instructions(effective_stages) + "\n\n" + _format_input(cm)
    debug(f"classify LLM call → {cm.proposed_id}")
    response = await llm.generate_content(prompt)
    parsed = parse_json(response)
    if parsed is None:
        raise ValueError(
            f"classifier returned non-JSON response for {cm.proposed_id}: {response[:200]!r}"
        )
    try:
        result = ClassificationResult.model_validate(parsed)
    except ValidationError as e:
        raise ValueError(
            f"classifier returned invalid result for {cm.proposed_id}: {e}"
        ) from e
    debug(
        f"classify LLM result ← {cm.proposed_id} stage_id={result.stage_id} "
        f"confidence={result.confidence:.2f} reason={result.reason!r}"
    )
    return result


async def classify_all(
    candidates: list[CandidateMilestone],
    llm: LLMClient,
    *,
    concurrency: int = 8,
    stages: tuple[StageDef, ...] | None = None,
) -> list[CandidateMilestone]:
    """Classify every candidate in parallel, returning a new list.

    On LLM error or invalid result, assign ``engagement`` as a neutral
    default and drop confidence to ``min(current, 0.3)`` so downstream
    code can see the milestone was a guess.
    """
    sem = asyncio.Semaphore(concurrency)

    async def _one(cm: CandidateMilestone) -> CandidateMilestone:
        async with sem:
            try:
                res = await classify_milestone(cm, llm, stages=stages)
            except Exception as e:  # noqa: BLE001
                warning(f"classify failed for {cm.proposed_id}: {e}")
                return cm.model_copy(
                    update={
                        "stage_id": "engagement",
                        "confidence": min(cm.confidence, 0.3),
                    }
                )

            stage_id = res.stage_id
            confidence = min(cm.confidence, res.confidence)
            if stage_id not in STAGE_IDS:
                warning(
                    f"classifier returned unknown stage_id {stage_id!r} for {cm.proposed_id}"
                )
                stage_id = "engagement"
                confidence = min(confidence, 0.3)
            return cm.model_copy(
                update={"stage_id": stage_id, "confidence": confidence}
            )

    return await asyncio.gather(*[_one(c) for c in candidates])
