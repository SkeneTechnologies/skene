"""Plan step definitions for configurable growth plan sections."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from skene.llm import LLMClient


@dataclass
class PlanStepDefinition:
    """A single configurable section of the growth plan."""

    title: str
    instruction: str


DEFAULT_PLAN_STEPS: list[PlanStepDefinition] = [
    PlanStepDefinition(
        title="The Growth Core",
        instruction=(
            "Strip the input to its fundamental analysis. Identify the Global Maximum — "
            "the single highest-leverage utility that drives compounding. Contrast against "
            "local maxima that teams typically optimize for. Be ruthless in selection."
        ),
    ),
    PlanStepDefinition(
        title="The Playbook (What?)",
        instruction=(
            "Define the high-leverage architectural shift. What does the Invisible Playbook "
            "look like? What moat does executing this build? Contrast against what average "
            "teams do. The answer must be non-obvious and elite."
        ),
    ),
    PlanStepDefinition(
        title="The Average Trap (Why?)",
        instruction=(
            "Contrast against the Common Path. Identify the exact failure point — the moment "
            "average teams diverge from the optimal trajectory. Apply V/T or LTV/CAC compounding "
            "logic to show why this divergence compounds against them over time."
        ),
    ),
    PlanStepDefinition(
        title="The Mechanics of Leverage (How?)",
        instruction=(
            "Detail the engineering of the move. Specify the four powers of leverage: "
            "Onboarding (first-action friction), Retention (habit loop), Virality (activation "
            "referral), Friction (deliberate removal). Be specific to the context — no generic advice."
        ),
    ),
]

_PARSE_STEPS_SYSTEM_PROMPT = """\
You are a growth plan architect. Your job is to interpret a user-written markdown file and \
produce structured plan section definitions.

The user has written freeform markdown describing what they want their growth plan to cover. \
Read their intent carefully and produce a JSON array where each item defines one plan section.

Rules:
- Return ONLY a JSON array, no commentary, no markdown fences.
- Each item must have exactly two string fields: "title" and "instruction".
- "title" is the section heading (short, punchy, e.g. "The Growth Core").
- "instruction" is a 1-3 sentence instruction for the LLM that will write that section \
(focus, what to analyze, what frameworks to apply).
- Preserve the user's ordering and intent.
- Return between 2 and 8 steps.
- Do NOT include Executive Summary or Technical Execution — those are added automatically.
"""


async def parse_plan_steps_with_llm(
    llm: LLMClient,
    file_content: str,
) -> list[PlanStepDefinition]:
    """Send plan-steps.md content to the LLM to produce step definitions.

    The LLM interprets freeform markdown and returns a JSON array
    of {title, instruction} objects. Falls back to DEFAULT_PLAN_STEPS
    on parse failure.

    Args:
        llm: LLM client for generation
        file_content: Raw content of plan-steps.md

    Returns:
        Parsed step definitions, or DEFAULT_PLAN_STEPS on failure
    """
    prompt = f"{_PARSE_STEPS_SYSTEM_PROMPT}\n\nUser's plan-steps.md content:\n\n{file_content}"
    try:
        response = await llm.generate_content(prompt)
        text = response.strip()
        fence_pattern = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL)
        match = fence_pattern.match(text)
        if match:
            text = match.group(1).strip()
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError("Expected a JSON array")
        steps = []
        for item in data:
            if not isinstance(item, dict):
                raise ValueError(f"Expected dict, got {type(item)}")
            title = item.get("title", "").strip()
            instruction = item.get("instruction", "").strip()
            if not title or not instruction:
                raise ValueError(f"Step missing title or instruction: {item}")
            steps.append(PlanStepDefinition(title=title, instruction=instruction))
        if not (2 <= len(steps) <= 8):
            raise ValueError(f"Expected 2-8 steps, got {len(steps)}")
        return steps
    except Exception:
        return DEFAULT_PLAN_STEPS


def load_plan_steps_file(context_dir: Path | None) -> str | None:
    """Find and read plan-steps.md content, or return None.

    Searches:
    1. context_dir/plan-steps.md if context_dir is provided
    2. ./skene-context/plan-steps.md as fallback

    Args:
        context_dir: Optional explicit context directory

    Returns:
        File content string, or None if not found
    """
    candidates: list[Path] = []
    if context_dir is not None:
        candidates.append(context_dir / "plan-steps.md")
    candidates.append(Path("skene-context") / "plan-steps.md")

    for path in candidates:
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8")
    return None


async def load_plan_steps(
    context_dir: Path | None,
    llm: LLMClient | None = None,
) -> list[PlanStepDefinition]:
    """Load plan steps: LLM-parsed from file, or defaults.

    If plan-steps.md is found and an LLM client is provided, the file
    content is sent to the LLM for interpretation. Otherwise falls back
    to DEFAULT_PLAN_STEPS.

    Args:
        context_dir: Optional explicit context directory to search for plan-steps.md
        llm: LLM client for parsing (required to use file-based steps)

    Returns:
        List of step definitions
    """
    file_content = load_plan_steps_file(context_dir)
    if file_content is not None and llm is not None:
        return await parse_plan_steps_with_llm(llm, file_content)
    return DEFAULT_PLAN_STEPS
