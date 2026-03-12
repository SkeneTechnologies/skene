"""Structural evaluation: deterministic checks on pipeline output."""

import json
from pathlib import Path

from loguru import logger

from benchmarks.evaluation.models import StructuralCheck, StructuralEvaluation
from benchmarks.runner.models import PipelineResult


def _check_pipeline_completion(result: PipelineResult) -> StructuralCheck:
    """Check that all pipeline steps completed with exit code 0."""
    if result.success:
        return StructuralCheck(check_name="pipeline_completion", passed=True, detail="All steps completed successfully")

    failed_steps = [s.step_name for s in result.steps if not s.success]
    return StructuralCheck(
        check_name="pipeline_completion",
        passed=False,
        detail=f"Failed steps: {', '.join(failed_steps)}",
    )


def _check_file_exists(output_dir: Path, relative_path: str) -> StructuralCheck:
    """Check that a specific file exists in the output directory."""
    full_path = output_dir / relative_path
    exists = full_path.exists()
    return StructuralCheck(
        check_name=f"file_exists:{relative_path}",
        passed=exists,
        detail=str(full_path) if not exists else "",
    )


def _check_growth_loops_exist(output_dir: Path) -> StructuralCheck:
    """Check that at least one growth loop JSON file exists."""
    loops_dir = output_dir / "growth-loops"
    if not loops_dir.exists():
        return StructuralCheck(
            check_name="file_exists:growth-loops/*.json",
            passed=False,
            detail=f"Directory not found: {loops_dir}",
        )
    loop_files = list(loops_dir.glob("*.json"))
    if not loop_files:
        return StructuralCheck(
            check_name="file_exists:growth-loops/*.json",
            passed=False,
            detail="No JSON files in growth-loops/",
        )
    return StructuralCheck(
        check_name="file_exists:growth-loops/*.json",
        passed=True,
        detail=f"Found {len(loop_files)} loop file(s)",
    )


def _check_json_valid(output_dir: Path, relative_path: str) -> StructuralCheck:
    """Check that a JSON file is valid."""
    full_path = output_dir / relative_path
    if not full_path.exists():
        return StructuralCheck(
            check_name=f"json_valid:{relative_path}",
            passed=False,
            detail="File does not exist",
        )
    try:
        json.loads(full_path.read_text())
        return StructuralCheck(check_name=f"json_valid:{relative_path}", passed=True)
    except json.JSONDecodeError as e:
        return StructuralCheck(
            check_name=f"json_valid:{relative_path}",
            passed=False,
            detail=str(e),
        )


def _check_template_schema(output_dir: Path) -> StructuralCheck:
    """Validate growth-template.json using the codebase's own validation function."""
    template_path = output_dir / "growth-template.json"
    if not template_path.exists():
        return StructuralCheck(
            check_name="template_schema",
            passed=False,
            detail="growth-template.json does not exist",
        )
    try:
        data = json.loads(template_path.read_text())
        from skene.templates.growth_template import _validate_template_structure

        _validate_template_structure(data)
        return StructuralCheck(check_name="template_schema", passed=True)
    except Exception as e:
        return StructuralCheck(
            check_name="template_schema",
            passed=False,
            detail=str(e)[:200],
        )


def _check_manifest_schema(output_dir: Path) -> StructuralCheck:
    """Validate growth-manifest.json against the GrowthManifest pydantic model."""
    manifest_path = output_dir / "growth-manifest.json"
    if not manifest_path.exists():
        return StructuralCheck(
            check_name="manifest_schema",
            passed=False,
            detail="growth-manifest.json does not exist",
        )
    try:
        data = json.loads(manifest_path.read_text())
        from skene.manifest import GrowthManifest

        GrowthManifest(**data)
        return StructuralCheck(check_name="manifest_schema", passed=True)
    except Exception as e:
        return StructuralCheck(
            check_name="manifest_schema",
            passed=False,
            detail=str(e)[:200],
        )


def _check_growth_loop_schema(output_dir: Path) -> list[StructuralCheck]:
    """Validate each growth loop JSON file against the expected schema."""
    loops_dir = output_dir / "growth-loops"
    if not loops_dir.exists():
        return [StructuralCheck(check_name="growth_loop_schema", passed=False, detail="growth-loops/ not found")]

    loop_files = sorted(loops_dir.glob("*.json"))
    if not loop_files:
        return [StructuralCheck(check_name="growth_loop_schema", passed=False, detail="No JSON files in growth-loops/")]

    import re

    checks: list[StructuralCheck] = []
    required_top = [
        "loop_id",
        "name",
        "description",
        "requirements",
        "dependencies",
        "verification_commands",
        "test_coverage",
        "metrics",
    ]
    required_reqs = ["files", "functions", "integrations", "telemetry"]

    for loop_file in loop_files:
        fname = loop_file.name
        try:
            data = json.loads(loop_file.read_text())
        except json.JSONDecodeError as e:
            checks.append(
                StructuralCheck(
                    check_name=f"growth_loop_schema:{fname}",
                    passed=False,
                    detail=f"Invalid JSON: {e}",
                )
            )
            continue

        missing_top = [f for f in required_top if f not in data]
        if missing_top:
            checks.append(
                StructuralCheck(
                    check_name=f"growth_loop_schema:{fname}",
                    passed=False,
                    detail=f"Missing fields: {', '.join(missing_top)}",
                )
            )
            continue

        # Validate loop_id format
        if not re.match(r"^[a-z0-9_]+$", data["loop_id"]):
            checks.append(
                StructuralCheck(
                    check_name=f"growth_loop_schema:{fname}",
                    passed=False,
                    detail=f"Invalid loop_id format: {data['loop_id']}",
                )
            )
            continue

        # Validate requirements sub-keys
        reqs = data["requirements"]
        missing_reqs = [f for f in required_reqs if f not in reqs]
        if missing_reqs:
            checks.append(
                StructuralCheck(
                    check_name=f"growth_loop_schema:{fname}",
                    passed=False,
                    detail=f"requirements missing: {', '.join(missing_reqs)}",
                )
            )
            continue

        checks.append(StructuralCheck(check_name=f"growth_loop_schema:{fname}", passed=True))

    return checks


def _check_markdown_length(output_dir: Path, relative_path: str, min_chars: int) -> StructuralCheck:
    """Check that a markdown file meets a minimum character length."""
    full_path = output_dir / relative_path
    if not full_path.exists():
        return StructuralCheck(
            check_name=f"markdown_length:{relative_path}",
            passed=False,
            detail="File does not exist",
        )
    content = full_path.read_text()
    length = len(content)
    passed = length >= min_chars
    return StructuralCheck(
        check_name=f"markdown_length:{relative_path}",
        passed=passed,
        detail=f"{length} chars (min: {min_chars})",
    )


def evaluate_structural(result: PipelineResult) -> StructuralEvaluation:
    """Run all structural checks on a pipeline result.

    Args:
        result: The pipeline result to evaluate.

    Returns:
        StructuralEvaluation with all check results.
    """
    logger.info(f"Evaluating: {result.codebase_name} / {result.model_name} / run-{result.run_number}")
    output_dir = result.output_dir
    checks: list[StructuralCheck] = []

    # Pipeline completion
    checks.append(_check_pipeline_completion(result))

    # File existence
    for path in ["growth-manifest.json", "growth-template.json", "growth-plan.md", ".skene-build-prompt.md"]:
        checks.append(_check_file_exists(output_dir, path))
    checks.append(_check_growth_loops_exist(output_dir))

    # JSON validity
    checks.append(_check_json_valid(output_dir, "growth-manifest.json"))
    checks.append(_check_json_valid(output_dir, "growth-template.json"))

    # Schema conformance
    checks.append(_check_manifest_schema(output_dir))
    checks.append(_check_template_schema(output_dir))

    # Growth loop schema
    checks.extend(_check_growth_loop_schema(output_dir))

    # Markdown length
    checks.append(_check_markdown_length(output_dir, "growth-plan.md", 500))
    checks.append(_check_markdown_length(output_dir, ".skene-build-prompt.md", 200))

    passed = sum(1 for c in checks if c.passed)
    total = len(checks)
    score = passed / total if total > 0 else 0.0

    logger.info(f"  -> {passed}/{total} checks passed (score: {score:.2f})")

    return StructuralEvaluation(
        codebase_name=result.codebase_name,
        model_name=result.model_name,
        run_number=result.run_number,
        checks=checks,
        total_checks=total,
        passed_checks=passed,
        score=round(score, 4),
    )
