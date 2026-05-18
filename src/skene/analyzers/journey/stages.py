"""The seven canonical journey stages.

These definitions drive the classifier in Step 4 and the layer/stage
assembly in :mod:`skene.analyzers.journey.assemble`. The order here is the
order milestones flow through the funnel.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StageDef:
    id: str
    order: int
    name: str
    subtitle: str
    description: str
    examples: list[str]


STAGES: tuple[StageDef, ...] = (
    StageDef(
        "discovery",
        1,
        "Discovery",
        "The Hook",
        "The user first encounters the product and decides to sign up. "
        "Public marketing routes, landing pages, and the signup flow itself "
        "belong here. Ends when an account exists.",
        ["Landing Page View", "Sign-Up Intent Triggered", "Account Created"],
    ),
    StageDef(
        "onboarding",
        2,
        "Onboarding",
        "The Setup",
        "The user configures the product so it can do useful work. API keys, "
        "integrations, initial settings, and required setup steps. Does not "
        "yet involve real user-facing output.",
        [
            "Admin Dashboard First Visit",
            "API Key Configured",
            "Onboarding Checklist Completed",
        ],
    ),
    StageDef(
        "activation",
        3,
        "Activation",
        "First Value",
        "The user receives the product's first real output. This is the aha "
        "moment — usually a single value event per product.",
        [
            "First AI Estimate Generated & Emailed",
            "First Chat Session Initiated",
            "First Lead Received",
        ],
    ),
    StageDef(
        "engagement",
        4,
        "Engagement",
        "Sticky Usage",
        "The user returns and uses the product repeatedly. Repeated writes "
        "to core domain tables, dashboard visits, and feature depth.",
        [
            "10+ Estimates Delivered",
            "Widget Deployed on Multiple Sites",
            "Leads Dashboard Used Weekly",
        ],
    ),
    StageDef(
        "retention",
        5,
        "Retention",
        "Habit Lock-In",
        "The user has formed a habit and is unlikely to churn. Long "
        "continuous activity windows, annual billing, renewal events.",
        [
            "30-Day Continuous Active Usage",
            "Annual Billing Adopted",
            "90-Day Retention Milestone",
        ],
    ),
    StageDef(
        "expansion",
        6,
        "Expansion",
        "More Value",
        "The user pays more or uses more of the product. Plan upgrades, additional seats, premium features.",
        [
            "Plan Tier Upgraded to Business",
            "White-Label Feature Activated",
            "API Access Configured",
        ],
    ),
    StageDef(
        "virality",
        7,
        "Virality",
        "The Loop",
        "The user brings other users to the product. Referrals, attribution links, public sharing, invites.",
        [
            "'Powered by' Link Active in Widget",
            "Referral Program Participation",
            "First Referred Sign-Up Converted",
        ],
    ),
)

STAGE_IDS: frozenset[str] = frozenset(s.id for s in STAGES)


def stage_by_id(stage_id: str) -> StageDef | None:
    for s in STAGES:
        if s.id == stage_id:
            return s
    return None


def stages_as_prompt(stages: tuple[StageDef, ...] = STAGES) -> str:
    """Markdown block listing each stage for use in classifier instructions.

    Accepts an optional ``stages`` override so a per-product specialization
    step can swap in domain-aware names/descriptions/examples while keeping
    the canonical ``id`` and ``order`` values.
    """
    blocks: list[str] = []
    for s in stages:
        examples = ", ".join(s.examples)
        blocks.append(f"- **{s.id}** ({s.name} — {s.subtitle})\n  {s.description}\n  Examples: {examples}")
    return "\n".join(blocks)
