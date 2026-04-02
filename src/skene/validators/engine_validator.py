"""Validation utilities for engine.yaml and generated trigger migrations."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from rich.table import Table

from skene.engine import default_engine_path, load_engine_document, parse_source_to_db_event
from skene.output import console


def _sanitize_feature_key(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_]+", "_", (value or "").lower()).strip("_")
    return cleaned or "feature"


@dataclass
class EngineFeatureCheck:
    key: str
    name: str
    source: str
    action_required: bool
    source_valid: bool
    migration_found: bool
    detail: str = ""

    @property
    def passed(self) -> bool:
        if not self.source_valid:
            return False
        if not self.action_required:
            return True
        return self.migration_found


@dataclass
class EngineValidationResult:
    project_root: Path
    engine_path: Path
    errors: list[str] = field(default_factory=list)
    feature_checks: list[EngineFeatureCheck] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        if self.errors:
            return False
        return all(check.passed for check in self.feature_checks)


def _read_migration_files(project_root: Path) -> list[tuple[Path, str]]:
    migrations_dir = project_root / "supabase" / "migrations"
    if not migrations_dir.exists():
        return []
    files = sorted(migrations_dir.glob("*.sql"))
    return [(path, path.read_text(encoding="utf-8")) for path in files]


def validate_engine(project_root: Path) -> EngineValidationResult:
    """Validate engine.yaml shape and action-trigger alignment with migrations."""
    project_root = project_root.resolve()
    engine_path = default_engine_path(project_root)
    result = EngineValidationResult(project_root=project_root, engine_path=engine_path)

    if not engine_path.exists():
        result.errors.append(f"Engine file not found: {engine_path}")
        return result

    try:
        engine_doc = load_engine_document(engine_path)
    except Exception as exc:
        result.errors.append(f"Failed to parse engine.yaml: {exc}")
        return result

    migration_files = _read_migration_files(project_root)

    for feature in engine_doc.features:
        parsed = parse_source_to_db_event(feature.source)
        action_required = feature.action is not None

        if parsed is None:
            result.feature_checks.append(
                EngineFeatureCheck(
                    key=feature.key,
                    name=feature.name,
                    source=feature.source,
                    action_required=action_required,
                    source_valid=False,
                    migration_found=False,
                    detail="Invalid source format. Expected schema.table.operation",
                )
            )
            continue

        _, table, operation = parsed
        if not action_required:
            result.feature_checks.append(
                EngineFeatureCheck(
                    key=feature.key,
                    name=feature.name,
                    source=feature.source,
                    action_required=False,
                    source_valid=True,
                    migration_found=False,
                    detail="Code-only feature (no action): trigger migration not required",
                )
            )
            continue

        safe_key = _sanitize_feature_key(feature.key)
        expected_trigger = f"skene_growth_trg_{table}_{operation}_{safe_key}"
        expected_function = f"skene_growth_fn_{table}_{operation}_{safe_key}"

        matched_files: list[str] = []
        for migration_path, content in migration_files:
            if expected_trigger in content and expected_function in content:
                matched_files.append(migration_path.name)

        if matched_files:
            latest = max(matched_files)
            rest = len(matched_files) - 1
            found_detail = f"Found in: {latest}" + (f" (+{rest})" if rest else "")
        else:
            found_detail = f"Missing trigger/function: {expected_trigger} / {expected_function}"

        result.feature_checks.append(
            EngineFeatureCheck(
                key=feature.key,
                name=feature.name,
                source=feature.source,
                action_required=True,
                source_valid=True,
                migration_found=bool(matched_files),
                detail=found_detail,
            )
        )

    return result


def print_engine_validation_report(result: EngineValidationResult) -> None:
    """Print engine validation report."""
    table = Table(title="Engine Status")
    table.add_column("Feature", style="cyan")
    table.add_column("Source", style="white")
    table.add_column("Mode", style="white")
    table.add_column("Status", style="white")
    table.add_column("Detail", style="white")

    if result.errors:
        for err in result.errors:
            table.add_row("-", "-", "-", "[red]error[/red]", err)
        console.print(table)
        return

    for item in result.feature_checks:
        mode = "action" if item.action_required else "code-only"
        status = "[green]ok[/green]" if item.passed else "[red]missing[/red]"
        table.add_row(item.name or item.key, item.source, mode, status, item.detail)

    if not result.feature_checks:
        table.add_row("-", "-", "-", "[yellow]warning[/yellow]", "No features found in engine.yaml")

    console.print(table)
