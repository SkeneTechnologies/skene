"""Factual evaluation: compare pipeline output against ground truth.

Checks how accurately the pipeline detected verifiable properties of the
codebase — tech stack, known features, industry classification, and
whether referenced file paths actually exist.
"""

import json
from pathlib import Path

from loguru import logger

from benchmarks.evaluation.ground_truth import GroundTruth
from benchmarks.evaluation.models import FactualCheck, FactualEvaluation
from benchmarks.runner.models import PipelineResult


def _normalize(value: str | None) -> str:
    """Normalize a string for fuzzy comparison (lowercase, strip whitespace)."""
    if value is None:
        return ""
    return value.strip().lower()


def _matches(expected: str | None, actual: str | None) -> bool:
    """Check if an actual value matches the expected value (case-insensitive, substring-aware).

    Handles common variations like "Next.js" vs "NextJS", "PostgreSQL" vs "Postgres".
    """
    e = _normalize(expected)
    a = _normalize(actual)
    if not e or not a:
        return False
    # Exact match
    if e == a:
        return True
    # Substring match (either direction)
    if e in a or a in e:
        return True
    # Strip dots and hyphens for things like "Next.js" vs "NextJS"
    e_stripped = e.replace(".", "").replace("-", "").replace(" ", "")
    a_stripped = a.replace(".", "").replace("-", "").replace(" ", "")
    if e_stripped == a_stripped:
        return True
    return False


def _check_tech_stack(manifest_data: dict, ground_truth: GroundTruth) -> list[FactualCheck]:
    """Check tech stack fields against ground truth."""
    checks: list[FactualCheck] = []
    gt_stack = ground_truth.tech_stack
    manifest_stack = manifest_data.get("tech_stack", {})

    # Check each specified field
    fields = ["framework", "language", "database", "auth", "deployment", "package_manager"]
    for field in fields:
        expected = getattr(gt_stack, field)
        if expected is None:
            continue  # Not specified in ground truth, skip

        actual = manifest_stack.get(field) or ""
        passed = _matches(expected, actual)
        checks.append(FactualCheck(
            check_name=f"tech_stack:{field}",
            category="tech_stack",
            passed=passed,
            expected=expected,
            actual=actual,
            detail=f"{'Match' if passed else 'Mismatch'}: expected '{expected}', got '{actual}'",
        ))

    # Check services (recall: how many expected services were detected?)
    if gt_stack.services:
        manifest_services = manifest_stack.get("services", [])
        manifest_services_lower = [_normalize(s) for s in manifest_services]
        for expected_service in gt_stack.services:
            found = any(_matches(expected_service, s) for s in manifest_services)
            checks.append(FactualCheck(
                check_name=f"tech_stack:service:{_normalize(expected_service)}",
                category="tech_stack",
                passed=found,
                expected=expected_service,
                actual=", ".join(manifest_services) if manifest_services else "(none)",
                detail=f"Service '{expected_service}' {'found' if found else 'not found'} in detected services",
            ))

    return checks


def _check_feature_detection(manifest_data: dict, ground_truth: GroundTruth) -> list[FactualCheck]:
    """Check whether expected features were detected.

    For each expected feature in ground truth, check if any detected
    growth feature matches by keyword or file pattern.
    """
    checks: list[FactualCheck] = []
    detected_features = manifest_data.get("current_growth_features", [])

    for gt_feature in ground_truth.expected_features:
        # Try to find a matching detected feature
        matched = False
        match_detail = ""

        for detected in detected_features:
            # Check keyword match in feature name or detected_intent
            feature_text = f"{detected.get('feature_name', '')} {detected.get('detected_intent', '')}".lower()
            keyword_match = any(kw.lower() in feature_text for kw in gt_feature.keywords) if gt_feature.keywords else False

            # Check file pattern match
            detected_path = detected.get("file_path", "")
            file_match = any(
                pattern.lower() in detected_path.lower()
                for pattern in gt_feature.file_patterns
            ) if gt_feature.file_patterns else False

            if keyword_match or file_match:
                matched = True
                match_detail = f"Matched detected feature '{detected.get('feature_name', '?')}'"
                break

        checks.append(FactualCheck(
            check_name=f"feature_detection:{gt_feature.name}",
            category="feature_detection",
            passed=matched,
            expected=gt_feature.name,
            actual=match_detail if matched else "(not detected)",
            detail=match_detail if matched else f"Feature '{gt_feature.name}' was not detected",
        ))

    return checks


def _check_industry(manifest_data: dict, ground_truth: GroundTruth) -> list[FactualCheck]:
    """Check industry classification against ground truth."""
    checks: list[FactualCheck] = []
    gt_industry = ground_truth.industry
    if gt_industry is None:
        return checks

    manifest_industry = manifest_data.get("industry") or {}
    actual_primary = manifest_industry.get("primary") or ""

    # Check primary industry
    acceptable = [gt_industry.primary] + gt_industry.acceptable_alternatives
    primary_match = any(_matches(acc, actual_primary) for acc in acceptable)
    checks.append(FactualCheck(
        check_name="industry:primary",
        category="industry",
        passed=primary_match,
        expected=gt_industry.primary,
        actual=actual_primary,
        detail=f"Acceptable: {acceptable}. Got: '{actual_primary}'",
    ))

    # Check expected tags in secondary
    actual_secondary = manifest_industry.get("secondary") or []
    for tag in gt_industry.expected_tags:
        found = any(_matches(tag, s) for s in actual_secondary)
        checks.append(FactualCheck(
            check_name=f"industry:tag:{_normalize(tag)}",
            category="industry",
            passed=found,
            expected=tag,
            actual=", ".join(actual_secondary) if actual_secondary else "(none)",
            detail=f"Tag '{tag}' {'found' if found else 'not found'} in secondary tags",
        ))

    return checks


def _check_file_references(manifest_data: dict, codebase_path: Path | None) -> list[FactualCheck]:
    """Check that file_path references in the manifest point to real files.

    This doesn't need ground truth — it checks against the actual codebase.
    """
    checks: list[FactualCheck] = []
    if codebase_path is None or not codebase_path.exists():
        return checks

    # Collect all file_path references from manifest
    file_paths: list[str] = []
    for feature in manifest_data.get("current_growth_features", []):
        fp = feature.get("file_path")
        if fp:
            file_paths.append(fp)
    for leak in manifest_data.get("revenue_leakage", []):
        fp = leak.get("file_path")
        if fp:
            file_paths.append(fp)

    if not file_paths:
        return checks

    valid_count = 0
    for fp in file_paths:
        # Try the path as-is relative to codebase
        resolved = codebase_path / fp
        exists = resolved.exists()
        if not exists:
            # Try stripping leading slash or common prefixes
            stripped = fp.lstrip("/")
            resolved = codebase_path / stripped
            exists = resolved.exists()

        if exists:
            valid_count += 1

    # Report as a single aggregate check (individual paths too noisy)
    total = len(file_paths)
    ratio = valid_count / total if total > 0 else 0.0
    checks.append(FactualCheck(
        check_name="file_references:validity",
        category="file_references",
        passed=ratio >= 0.5,  # Pass if at least half of referenced files exist
        expected=f"{total} file paths should exist",
        actual=f"{valid_count}/{total} exist ({ratio:.0%})",
        detail=f"{valid_count} of {total} referenced file paths exist in the codebase",
    ))

    return checks


def _compute_category_scores(checks: list[FactualCheck]) -> dict[str, float]:
    """Compute per-category scores from a list of checks."""
    category_counts: dict[str, tuple[int, int]] = {}  # category -> (passed, total)
    for check in checks:
        passed, total = category_counts.get(check.category, (0, 0))
        category_counts[check.category] = (passed + (1 if check.passed else 0), total + 1)

    return {
        category: round(passed / total, 4) if total > 0 else 0.0
        for category, (passed, total) in category_counts.items()
    }


def evaluate_factual(
    result: PipelineResult,
    ground_truth: GroundTruth,
    codebase_path: Path | None = None,
) -> FactualEvaluation:
    """Run all factual checks on a pipeline result against ground truth.

    Args:
        result: The pipeline result to evaluate.
        ground_truth: Ground truth data for the codebase.
        codebase_path: Path to the codebase (for file reference validation).

    Returns:
        FactualEvaluation with all check results and category scores.
    """
    logger.info(f"Factual eval: {result.codebase_name} / {result.model_name} / run-{result.run_number}")

    # Load manifest data
    manifest_path = result.output_dir / "growth-manifest.json"
    if not manifest_path.exists():
        logger.warning(f"  -> No growth-manifest.json found, skipping factual evaluation")
        return FactualEvaluation(
            codebase_name=result.codebase_name,
            model_name=result.model_name,
            run_number=result.run_number,
            checks=[],
            total_checks=0,
            passed_checks=0,
            score=0.0,
            category_scores={},
        )

    manifest_data = json.loads(manifest_path.read_text())
    checks: list[FactualCheck] = []

    # Run all check categories
    checks.extend(_check_tech_stack(manifest_data, ground_truth))
    checks.extend(_check_feature_detection(manifest_data, ground_truth))
    checks.extend(_check_industry(manifest_data, ground_truth))
    checks.extend(_check_file_references(manifest_data, codebase_path))

    passed = sum(1 for c in checks if c.passed)
    total = len(checks)
    score = passed / total if total > 0 else 0.0
    category_scores = _compute_category_scores(checks)

    logger.info(f"  -> {passed}/{total} checks passed (score: {score:.2f})")
    for cat, cat_score in category_scores.items():
        logger.info(f"     {cat}: {cat_score:.0%}")

    return FactualEvaluation(
        codebase_name=result.codebase_name,
        model_name=result.model_name,
        run_number=result.run_number,
        checks=checks,
        total_checks=total,
        passed_checks=passed,
        score=round(score, 4),
        category_scores=category_scores,
    )
