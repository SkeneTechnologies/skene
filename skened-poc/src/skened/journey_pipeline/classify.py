"""Stage classification — assign each candidate one of the seven canonical stages.

Two implementations behind the ``Classifier`` seam:

- ``HeuristicClassifier`` (default, offline): ordered keyword rules mirroring the priority
  order of the reference LLM classifier (monetization → expansion, virality → virality,
  first-value → activation, lifecycle ambiguity → earlier stage, else engagement).
- ``LlmClassifier``: faithful port of the reference per-milestone LLM call, using an
  ``LLMClient`` (e.g. LiteLLM-backed). Ready to swap in once credentials are configured.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Protocol

from .candidate import CandidateMilestone
from .llm import LlmAnalysisError
from .stages import STAGE_IDS, STAGES, StageDef, stages_as_prompt

logger = logging.getLogger("skened.pipeline.classify")


class Classifier(Protocol):
    async def classify(self, candidates: list[CandidateMilestone]) -> list[CandidateMilestone]: ...


# --- heuristic (default) -------------------------------------------------------
# Ordered: first matching rule wins. Mirrors the reference classifier's priority order.
_RULES: tuple[tuple[str, float, re.Pattern], ...] = (
    ("expansion", 0.8, re.compile(r"payment|billing|checkout|subscription|stripe|paddle|invoice|upgrade|\bplan\b|\bseat\b|paywall|premium|pricing|overage", re.I)),
    ("virality", 0.8, re.compile(r"referral|\binvite\b|\bshare\b|public[\s_-]?link|attribution|\bembed\b|\baffiliate\b|utm_", re.I)),
    ("discovery", 0.75, re.compile(r"sign[\s_-]?up|signup|\bregister\b|\blogin\b|sign[\s_-]?in|oauth|\bsso\b|magic[\s_-]?link|landing|\bauth\b|\bmarketing\b", re.I)),
    ("onboarding", 0.7, re.compile(r"onboard|\bsetup\b|configure|\bsettings\b|\bprofile\b|integration|api[\s_-]?key|\bconnect\b|\binstall\b", re.I)),
    ("activation", 0.7, re.compile(r"\bcreate\b|generate|\bfirst\b|\bsend\b|\bemail\b|\bestimate\b|\blead\b|\bnew\b|\bsubmit\b", re.I)),
    ("retention", 0.7, re.compile(r"\brenew|retention|annual|\bhabit\b|\bstreak\b", re.I)),
    ("engagement", 0.7, re.compile(r"comment|reaction|dashboard|\blist\b|\bview\b|\bupdate\b|\bedit\b|\bdelete\b|analytics|\bevent\b|\btrack\b|export|\breport\b|background|\bjob\b|\bcron\b", re.I)),
)
_DEFAULT_STAGE = "engagement"
_DEFAULT_CONFIDENCE = 0.3


def _candidate_text(cm: CandidateMilestone) -> str:
    parts = [cm.name, cm.description, cm.tracked_event or ""]
    for ev in cm.evidence:
        parts.append(ev.path or ev.table or "")
        parts.append(ev.reason)
    return " ".join(parts)


class HeuristicClassifier:
    async def classify(self, candidates: list[CandidateMilestone]) -> list[CandidateMilestone]:
        out: list[CandidateMilestone] = []
        for cm in candidates:
            text = _candidate_text(cm)
            stage_id, conf = _DEFAULT_STAGE, _DEFAULT_CONFIDENCE
            for sid, rule_conf, pattern in _RULES:
                if pattern.search(text):
                    stage_id, conf = sid, rule_conf
                    break
            # Final confidence is the lower of the extractor's and the classifier's —
            # matches the reference pipeline's conservative capping.
            out.append(cm.model_copy(update={
                "stage_id": stage_id,
                "confidence": round(min(cm.confidence, conf), 4),
            }))
        return out


# --- LLM-backed (migration target) ---------------------------------------------
_LLM_INSTRUCTIONS = """\
You classify a single user-journey milestone into one of seven stages.

Stages:
{stages}

Rules, applied in order — the first matching rule wins:
1. Monetization signal → 'expansion' (payment, billing, checkout, subscription, plan
   upgrade, seat addition, paid feature unlock, usage overage).
2. Virality signal → 'virality' (referrals, invites, share links, public pages,
   attribution, embeds with attribution).
3. First real value → 'activation' (the user receiving the product's primary output for
   the first time).
4. Lifecycle ambiguity → earlier in the funnel (discovery vs onboarding, onboarding vs
   activation, engagement vs retention — prefer the earlier). Does NOT apply to expansion
   or virality.
5. Set confidence < 0.7 when genuinely ambiguous.

Return ONLY a JSON object, no prose, no markdown, no code fences:
{{"stage_id": "<one of {ids}>", "confidence": <0.0..1.0>, "reason": "<short>"}}
"""


def _format_input(cm: CandidateMilestone) -> str:
    lines = [f"- {ev.source.value}: {ev.path or ev.table or '?'} — {ev.reason}" for ev in cm.evidence]
    return (
        f"Milestone: {cm.name}\n"
        f"Description: {cm.description}\n"
        f"Tracked event: {cm.tracked_event or '(none)'}\n"
        f"Evidence:\n" + "\n".join(lines)
    )


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.I | re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            return json.loads(m.group(0))
        raise


class LlmClassifier:
    """Per-milestone LLM classification. Faithful to the reference prompt and fallbacks."""

    def __init__(self, llm, concurrency: int = 8, stages: tuple[StageDef, ...] = STAGES) -> None:
        self._llm = llm
        self._sem = asyncio.Semaphore(max(1, concurrency))
        self._stages = stages
        self._instructions = _LLM_INSTRUCTIONS.format(
            stages=stages_as_prompt(stages), ids=sorted(STAGE_IDS))

    async def classify(self, candidates: list[CandidateMilestone]) -> list[CandidateMilestone]:
        return list(await asyncio.gather(*(self._classify_one(cm) for cm in candidates)))

    async def _classify_one(self, cm: CandidateMilestone) -> CandidateMilestone:
        async with self._sem:
            try:
                raw = await self._llm.complete(_format_input(cm), system=self._instructions)
                data = _parse_json(raw)
                stage_id = data["stage_id"]
                conf = float(data["confidence"])
            except Exception as e:  # noqa: BLE001 — fail the run; do not silently default
                raise LlmAnalysisError(f"LLM classification failed for {cm.proposed_id!r}: {e}") from e
            if stage_id not in STAGE_IDS:
                raise LlmAnalysisError(
                    f"LLM returned unknown stage_id {stage_id!r} for {cm.proposed_id!r}"
                )
            return cm.model_copy(update={
                "stage_id": stage_id,
                "confidence": round(min(cm.confidence, conf), 4),
            })
