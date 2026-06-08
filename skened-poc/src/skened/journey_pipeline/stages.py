"""The seven canonical journey stages and the 4-layer swimlane model.

Ported from the reference ``analyze-journey`` pipeline. The order here is the order
milestones flow through the funnel. These definitions drive the classifier and the
stage/layer assembly.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StageDef:
    id: str
    order: int
    name: str
    subtitle: str
    description: str
    examples: list[str] = field(default_factory=list)


STAGES: tuple[StageDef, ...] = (
    StageDef("discovery", 1, "Discovery", "The Hook",
             "The user first encounters the product and decides to sign up. Public marketing "
             "routes, landing pages, and the signup flow itself belong here.",
             ["Landing Page View", "Sign-Up Intent Triggered", "Account Created"]),
    StageDef("onboarding", 2, "Onboarding", "The Setup",
             "The user configures the product so it can do useful work. API keys, integrations, "
             "initial settings, and required setup steps.",
             ["API Key Configured", "Integration Connected", "Onboarding Checklist Completed"]),
    StageDef("activation", 3, "Activation", "First Value",
             "The user receives the product's first real output — the aha moment.",
             ["First Estimate Generated", "First Chat Session", "First Lead Received"]),
    StageDef("engagement", 4, "Engagement", "Sticky Usage",
             "The user returns and uses the product repeatedly. Repeated writes to core domain "
             "tables, dashboard visits, feature depth.",
             ["10+ Items Delivered", "Dashboard Used Weekly", "Comments & Reactions"]),
    StageDef("retention", 5, "Retention", "Habit Lock-In",
             "The user has formed a habit and is unlikely to churn. Long activity windows, "
             "annual billing, renewal events.",
             ["30-Day Continuous Usage", "Annual Billing Adopted", "Renewal"]),
    StageDef("expansion", 6, "Expansion", "More Value",
             "The user pays more or uses more of the product. Plan upgrades, seats, premium "
             "features.",
             ["Plan Upgraded", "Seats Added", "Premium Feature Activated"]),
    StageDef("virality", 7, "Virality", "The Loop",
             "The user brings other users to the product. Referrals, attribution links, public "
             "sharing, invites.",
             ["Referral Sent", "Public Share Link Created", "Referred Sign-Up Converted"]),
)

STAGE_IDS: frozenset[str] = frozenset(s.id for s in STAGES)

# Standard 4-layer swimlane model: a coarse grouping of the seven stages.
DEFAULT_LAYERS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("L1", "Acquisition", ("discovery",)),
    ("L2", "Onboarding & Activation", ("onboarding", "activation")),
    ("L3", "Engagement & Retention", ("engagement", "retention")),
    ("L4", "Growth", ("expansion", "virality")),
)


def stages_as_prompt(stages: tuple[StageDef, ...] = STAGES) -> str:
    """Markdown block listing each stage, for use in LLM classifier instructions."""
    blocks: list[str] = []
    for s in stages:
        examples = ", ".join(s.examples)
        blocks.append(f"- **{s.id}** ({s.name} — {s.subtitle})\n  {s.description}\n  Examples: {examples}")
    return "\n".join(blocks)
