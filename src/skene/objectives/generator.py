"""
LLM-driven growth objectives generation.

Generates 3 prioritized growth objectives based on manifest and template data.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from skene.llm.base import LLMClient


def _build_prompt(
    manifest_data: dict[str, Any],
    template_data: dict[str, Any],
    quarter: str | None = None,
    guidance: str | None = None,
) -> str:
    """Build a prompt for generating growth objectives."""
    manifest_json = json.dumps(manifest_data, indent=2, default=str)
    template_json = json.dumps(template_data, indent=2, default=str)

    quarter_context = f"for {quarter}" if quarter else "for the current period"

    guidance_section = ""
    if guidance:
        guidance_section = f"""

## User Guidance:
{guidance}

**IMPORTANT:**
 - Prioritize objectives that align with the user's guidance above
 - The user's guidance should strongly influence which lifecycle stages and metrics you select
"""

    return f"""You are a Product-Led Growth (PLG) strategist. Your task is to analyze the project manifest and growth
template to identify the 3 most impactful growth objectives {quarter_context}.

## Project Manifest (Current State):
{manifest_json}

## Growth Template (Available Lifecycles & Metrics):
{template_json}{guidance_section}

## Your Task:

Based on the manifest data (tech stack, growth hubs, GTM gaps) and the available lifecycle metrics from the template,
select exactly 3 growth objectives that would have the highest impact.

For each objective:
1. Choose a lifecycle stage from the template (e.g., ACQUISITION, ACTIVATION, RETENTION, etc.)
2. Select the most relevant metric from that lifecycle's metrics array
3. Set a specific, achievable target based on the healthyBenchmark
4. Define a tolerance range (typically +/- 5-20% depending on the metric)

Prioritize objectives that:
- Address gaps identified in the manifest's growth_opportunities
- Align with the project's current growth features
- Are measurable and actionable
- Cover different lifecycle stages for balanced growth

Return your response as a JSON array with exactly 3 objects:
```json
[
  {{
    "lifecycle": "LIFECYCLE_NAME",
    "metric": "Metric Name",
    "target": "Specific target value",
    "tolerance": "Tolerance range description"
  }},
  ...
]
```

Return ONLY the JSON array, no other text or markdown code blocks.
"""


def _parse_json_response(response: str) -> list[dict[str, Any]]:
    """Parse JSON array from LLM response."""
    response = response.strip()

    # Try direct JSON parse first
    try:
        parsed = json.loads(response)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code fence
    json_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", response, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(1).strip())
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

    # Try finding JSON array in text
    arr_match = re.search(r"(\[.*\])", response, re.DOTALL)
    if arr_match:
        try:
            parsed = json.loads(arr_match.group(1).strip())
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

    raise ValueError("Could not parse LLM response as JSON array.")


def _validate_objectives(objectives: list[dict[str, Any]]) -> None:
    """Validate that objectives have required fields."""
    if len(objectives) != 3:
        logger.warning(f"Expected 3 objectives, got {len(objectives)}")

    required_fields = ["lifecycle", "metric", "target", "tolerance"]
    for i, obj in enumerate(objectives):
        missing = [field for field in required_fields if field not in obj]
        if missing:
            raise ValueError(f"Objective {i + 1} missing required fields: {missing}")


def _format_markdown(
    objectives: list[dict[str, Any]],
    quarter: str | None = None,
) -> str:
    """Format objectives as markdown."""
    title = f"# Growth Objectives {quarter}" if quarter else "# Growth Objectives"
    generated_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        title,
        "",
        f"*Generated on {generated_date}*",
        "",
    ]

    for obj in objectives:
        lifecycle = obj.get("lifecycle", "Unknown")
        metric = obj.get("metric", "Unknown")
        target = obj.get("target", "TBD")
        tolerance = obj.get("tolerance", "TBD")

        lines.extend(
            [
                f"## {lifecycle}",
                f"- **Metric:** {metric}",
                f"- **Target:** {target}",
                f"- **Tolerance:** {tolerance}",
                "",
            ]
        )

    lines.append("---")
    lines.append("*Growth objectives generated by skene.*")

    return "\n".join(lines)


async def generate_objectives(
    llm: LLMClient,
    manifest_data: dict[str, Any],
    template_data: dict[str, Any],
    quarter: str | None = None,
    guidance: str | None = None,
) -> str:
    """
    Generate growth objectives markdown from manifest and template data.

    Args:
        llm: LLM client for generation
        manifest_data: Project manifest data (from growth-manifest.json)
        template_data: Growth template data (from growth-template.json)
        quarter: Optional quarter label (e.g., "Q1", "Q2 2024")
        guidance: Optional guidance text to influence objective selection

    Returns:
        Formatted markdown string with 3 growth objectives
    """
    prompt = _build_prompt(manifest_data, template_data, quarter, guidance)

    logger.info(f"Generating growth objectives{' for ' + quarter if quarter else ''}...")
    response = await llm.generate_content(prompt)

    objectives = _parse_json_response(response)
    _validate_objectives(objectives)

    markdown = _format_markdown(objectives, quarter)

    logger.success(f"Generated {len(objectives)} growth objectives")
    return markdown


def write_objectives_output(
    markdown_content: str,
    output_path: Path | str,
) -> Path:
    """
    Write objectives markdown to file.

    Args:
        markdown_content: Formatted markdown content
        output_path: Path to write the file

    Returns:
        Path to the written file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown_content)

    logger.info(f"Wrote growth objectives to {output_path}")
    return output_path
