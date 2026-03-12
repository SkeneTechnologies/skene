"""
LLM-driven growth template generation with flexible structure based on business type.
Templates are used as examples, not rigid structures.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from skene.llm.base import LLMClient

EXAMPLE_TEMPLATES_DIR = Path("src") / "templates"


def _resolve_templates_dir() -> Path:
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / EXAMPLE_TEMPLATES_DIR


def load_example_templates() -> list[dict[str, Any]]:
    """Load all example templates to use as reference."""
    templates_dir = _resolve_templates_dir()
    example_templates = []

    if templates_dir.exists():
        for template_file in templates_dir.glob("*-template.json"):
            try:
                template_data = json.loads(template_file.read_text())
                example_templates.append(template_data)
                logger.debug(f"Loaded example template: {template_file.name}")
            except Exception as e:
                logger.warning(f"Failed to load template {template_file}: {e}")

    return example_templates


def _build_prompt(
    manifest_data: dict[str, Any],
    business_type: str | None = None,
    example_templates: list[dict[str, Any]] | None = None,
) -> str:
    """Build a prompt that allows flexible template generation based on business type."""

    # Use the first example template as the primary reference
    example_template = example_templates[0] if example_templates else None
    example_json = json.dumps(example_template, indent=2) if example_template else "{}"

    # Create manifest description from the manifest data
    manifest_description = json.dumps(manifest_data, indent=2, default=str)

    business_context = f"Business type: {business_type}" if business_type else "Infer business type from manifest"

    return (
        "You are a Product-Led Growth (PLG) template designer. Your task is to create a custom PLG "
        "template structure based on the provided manifest, using the example template as a reference.\n\n"
        "## Example Template Structure (Reference):\n"
        f"{example_json}\n\n"
        "## Manifest Data (User's Project):\n"
        f"{manifest_description}\n\n"
        f"## Business Type Context:\n"
        f"{business_context}\n\n"
        "Based on the manifest data, create a custom PLG template that:\n"
        "1. Follows the same JSON structure as the example template\n"
        "2. Has 3-7 lifecycle stages that match the business model and user journey from the manifest\n"
        "3. Each lifecycle MUST include:\n"
        '   - A descriptive name (UPPERCASE, e.g., "DISCOVERY", "ONBOARDING", "ACTIVATION")\n'
        '   - A short description (1-3 words, e.g., "The Hook", "The Trust", "First Value")\n'
        "   - An order_index (1, 2, 3, etc.)\n"
        "   - 3-7 milestones, each with:\n"
        "     * A clear title\n"
        "     * A descriptive description\n"
        "     * An order_index\n"
        '   - **CRITICAL: A "metrics" array with 3-5 metrics**, each metric must have:\n'
        '     * name: A clear metric name (e.g., "Conversion Rate", "Time to Value")\n'
        "     * howToMeasure: A specific description of how to measure this metric\n"
        "     * healthyBenchmark: A benchmark value indicating what's considered healthy "
        '(e.g., "> 25%", "< 4 hours")\n\n'
        "4. The lifecycles should represent the complete user journey from first contact to long-term value\n"
        "5. Milestones should be specific, actionable, and measurable\n"
        "6. Metrics should be relevant to each lifecycle stage and help track performance\n"
        "7. Use terminology and concepts that match the business model identified in the manifest\n\n"
        '**IMPORTANT**: Every lifecycle MUST include a "metrics" array. Look at the example template - '
        "each lifecycle has metrics that measure performance for that stage. Your generated template must "
        "follow this pattern.\n\n"
        "Return ONLY a valid JSON object matching the example structure. Do not include markdown code blocks. "
        "The JSON should have:\n"
        "- title: A descriptive title for the template\n"
        "- description: A brief description of what this template tracks (derived from manifest)\n"
        '- version: "1.0.0"\n'
        "- framework: A short name for the framework\n"
        "- lifecycles: Array of lifecycle objects (each MUST include a metrics array)\n"
        "- metadata: Object with framework_description, usage, and category (created_at will be set automatically)\n\n"
        "Be creative but practical. The template should be immediately usable for tracking PLG metrics.\n"
    )


def _parse_json_response(response: str) -> dict[str, Any]:
    """Parse JSON from LLM response, handling various formats."""
    response = response.strip()

    # Try direct JSON parse first
    try:
        parsed = json.loads(response)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code fence
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(1).strip())
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # Try finding JSON object in text
    obj_match = re.search(r"(\{.*\})", response, re.DOTALL)
    if obj_match:
        try:
            parsed = json.loads(obj_match.group(1).strip())
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    raise ValueError("Could not parse LLM response as JSON.")


def _validate_template_structure(template: dict[str, Any]) -> None:
    """Validate that the generated template has required fields and proper structure."""
    required_fields = ["title", "description", "version", "framework", "lifecycles", "metadata"]
    missing = [field for field in required_fields if field not in template]

    if missing:
        raise ValueError(f"Generated template missing required fields: {missing}")

    # Validate lifecycles structure
    if not isinstance(template.get("lifecycles"), list):
        raise ValueError("Template 'lifecycles' must be an array")

    if len(template["lifecycles"]) < 3 or len(template["lifecycles"]) > 7:
        logger.warning(f"Template has {len(template['lifecycles'])} lifecycles (recommended: 3-7)")

    # Validate each lifecycle
    for i, lifecycle in enumerate(template["lifecycles"]):
        lifecycle_name = lifecycle.get("name", f"lifecycle_{i}")

        required_lifecycle_fields = ["name", "description", "order_index", "milestones", "metrics"]
        missing_lifecycle = [field for field in required_lifecycle_fields if field not in lifecycle]

        if missing_lifecycle:
            raise ValueError(f"Lifecycle '{lifecycle_name}' missing required fields: {missing_lifecycle}")

        # Validate milestones
        if not isinstance(lifecycle.get("milestones"), list):
            raise ValueError(f"Lifecycle '{lifecycle_name}' milestones must be an array")

        if len(lifecycle["milestones"]) < 3 or len(lifecycle["milestones"]) > 7:
            logger.warning(
                f"Lifecycle '{lifecycle_name}' has {len(lifecycle['milestones'])} milestones (recommended: 3-7)"
            )

        # CRITICAL: Validate metrics array exists
        if not isinstance(lifecycle.get("metrics"), list):
            raise ValueError(
                f"**CRITICAL**: Lifecycle '{lifecycle_name}' is missing 'metrics' array. "
                "Each lifecycle MUST have a metrics array with 3-5 metrics."
            )

        if len(lifecycle["metrics"]) < 3 or len(lifecycle["metrics"]) > 5:
            logger.warning(f"Lifecycle '{lifecycle_name}' has {len(lifecycle['metrics'])} metrics (recommended: 3-5)")

        # Validate each metric has required fields
        for j, metric in enumerate(lifecycle["metrics"]):
            required_metric_fields = ["name", "howToMeasure", "healthyBenchmark"]
            missing_metric = [field for field in required_metric_fields if field not in metric]

            if missing_metric:
                raise ValueError(f"Lifecycle '{lifecycle_name}', metric {j}: missing fields {missing_metric}")

    # Validate metadata
    if not isinstance(template.get("metadata"), dict):
        raise ValueError("Template 'metadata' must be an object")

    logger.info(f"✓ Generated template '{template['title']}' with {len(template['lifecycles'])} lifecycle stages")
    logger.info("✓ All lifecycles include required metrics arrays")


async def generate_growth_template(
    llm: LLMClient,
    manifest_data: dict[str, Any],
    business_type: str | None = None,
) -> dict[str, Any]:
    """
    Generate a custom growth template tailored to the business type.

    Args:
        llm: LLM client for generation
        manifest_data: Project manifest data
        business_type: Optional business type (e.g., "design-agency", "b2b-saas")
                      If not provided, LLM will infer from manifest

    Returns:
        Custom growth template dictionary
    """
    example_templates = load_example_templates()
    prompt = _build_prompt(manifest_data, business_type, example_templates)

    logger.info(f"Generating custom growth template{' for ' + business_type if business_type else ''}...")
    response = await llm.generate_content(prompt)

    parsed = _parse_json_response(response)
    _validate_template_structure(parsed)

    # Set the created_at date to the current date
    if "metadata" in parsed and isinstance(parsed["metadata"], dict):
        parsed["metadata"]["created_at"] = datetime.now().strftime("%Y-%m-%d")

    template_name = parsed.get("title", parsed.get("name", "Unknown"))
    stage_count = len(parsed.get("lifecycles", parsed.get("keywordMappings", {})))
    logger.success(f"Generated template: {template_name} with {stage_count} stages")
    return parsed


def write_growth_template_outputs(
    template_data: dict[str, Any],
    output_dir: Path | str,
) -> Path:
    """
    Write growth template to JSON file.

    Args:
        template_data: The growth template data to write
        output_dir: Directory to write files to

    Returns:
        Path to the JSON file
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write JSON file
    json_path = output_dir / "growth-template.json"
    json_path.write_text(json.dumps(template_data, indent=2))
    logger.info(f"Wrote growth template to {json_path}")

    return json_path
