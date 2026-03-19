"""Structured schema for council memo (growth plan) output."""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field


class TechnicalExecution(BaseModel):
    """Technical Execution: focused, short specifications for implementation."""

    overview: str = Field(description="1-2 sentence overview with confidence, e.g. 'Implement X. Confidence: 95%'")
    what_we_building: str = Field(description="Short numbered list (3-5 items) of what we're building")
    tasks: str = Field(description="Most important technical tasks only, short numbered list, no phase grouping")
    data_triggers: str = Field(description="Events/conditions that trigger the flow (brief)")
    success_metrics: str = Field(description="Primary success metrics (brief)")


class PlanSection(BaseModel):
    """A numbered section of the growth plan memo."""

    title: str = Field(description="Section heading, e.g. 'The Next Action'")
    content: str = Field(description="Free-form markdown content")


class GrowthPlan(BaseModel):
    """Complete structured growth plan."""

    executive_summary: str = Field(description="High-level summary focused on first-time activation")
    sections: list[PlanSection] = Field(description="Plan sections (dynamic, driven by step definitions)")
    technical_execution: TechnicalExecution = Field(description="Technical Execution blueprint")


def render_plan_to_markdown(plan: GrowthPlan, generated_at: str, project_name: str | None = None) -> str:
    """Render a GrowthPlan to the markdown memo format.

    Args:
        plan: Validated GrowthPlan instance
        generated_at: ISO timestamp string
        project_name: Project name from manifest file (None = omit from output)

    Returns:
        Markdown string matching the council memo format
    """
    lines: list[str] = []

    if project_name:
        lines.append(f"# Growth Plan: {project_name} #")
    else:
        lines.append("# Growth Plan #")
    lines.append(f"**Generated:** {generated_at}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Executive Summary (disabled)
    # lines.append("## Executive Summary")
    # lines.append("")
    # lines.append(plan.executive_summary)
    # lines.append("")

    # Dynamic sections (exclude Technical Execution — it is rendered separately)
    sections = [s for s in plan.sections if s.title.lower() != "technical execution"]
    section_count = len(sections)
    te_number = section_count + 1
    for i, section in enumerate(sections, start=1):
        lines.append(f"### {i}. {section.title}")
        lines.append("")
        lines.append(section.content)
        lines.append("")

    # Technical Execution
    te = plan.technical_execution
    lines.append(f"### {te_number}. Technical Execution")
    lines.append("")
    lines.append(f"**Overview**\n{te.overview}")
    lines.append("")
    lines.append(f"**What We're Building**\n{te.what_we_building}")
    lines.append("")
    lines.append(f"**Technical Tasks**\n{te.tasks}")
    lines.append("")
    lines.append(f"**Data Triggers**\n{te.data_triggers}")
    lines.append("")
    lines.append(f"**Success Metrics**\n{te.success_metrics}")
    lines.append("")

    return "\n".join(lines)


def parse_plan_json(response: str) -> GrowthPlan:
    """Parse an LLM response as JSON into a GrowthPlan.

    Strips markdown code fences (```json ... ```) if present,
    then validates with Pydantic.

    Args:
        response: Raw LLM response text

    Returns:
        Validated GrowthPlan instance

    Raises:
        ValueError: If JSON is invalid or doesn't match schema
    """
    text = response.strip()

    # Strip code fences
    fence_pattern = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL)
    match = fence_pattern.match(text)
    if match:
        text = match.group(1).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM response is not valid JSON: {e}") from e

    try:
        return GrowthPlan.model_validate(data)
    except Exception as e:
        raise ValueError(f"JSON does not match GrowthPlan schema: {e}") from e
