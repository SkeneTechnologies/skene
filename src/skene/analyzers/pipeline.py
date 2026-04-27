"""
Unified journey pipeline: schema → growth → plan.

The three analysis steps (``analyse-journey``, ``analyse-growth-from-schema``,
``analyse-plan``) are composable phases of a single pipeline. This module owns
the chain so CLI commands stay thin.

Each stage produces a typed outcome (``StageOutcome``) that records what was
written, a human-readable summary, and whether the stage succeeded, was
skipped, or failed. The orchestrator never raises on stage errors — it
captures them in the outcome so the CLI can print a single summary at the
end.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from skene.analyzers.growth_from_schema import GrowthState, analyse_growth_from_schema
from skene.analyzers.journey_compiler import JourneyState, compile_user_journey
from skene.analyzers.plan_engine import DEFAULT_FEATURE_COUNT, PlanState, plan_engine_from_manifest
from skene.analyzers.schema_journey import SchemaState, analyse_journey
from skene.llm import LLMClient


class Stage(str, Enum):
    """Identifier for each pipeline phase."""

    SCHEMA = "schema"
    GROWTH = "growth"
    PLAN = "plan"
    JOURNEY = "journey"


class StageStatus(str, Enum):
    """Terminal status for a single stage."""

    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class StageOutcome:
    """Report of a single stage: what was produced and how it went."""

    stage: Stage
    status: StageStatus
    artifact: Path | None = None
    summary: str = ""
    error: str | None = None


@dataclass
class PipelinePaths:
    """Resolved output paths for every artifact the pipeline may write."""

    schema: Path
    growth: Path
    engine: Path
    new_features: Path
    journey: Path


@dataclass
class PipelineResult:
    """Final report of a pipeline run."""

    outcomes: list[StageOutcome] = field(default_factory=list)
    schema: SchemaState | None = None
    growth: GrowthState | None = None
    plan: PlanState | None = None
    journey: JourneyState | None = None

    @property
    def failed(self) -> bool:
        return any(o.status is StageStatus.FAILED for o in self.outcomes)

    def outcome_for(self, stage: Stage) -> StageOutcome | None:
        return next((o for o in self.outcomes if o.stage is stage), None)


# ---------------------------------------------------------------------------
# Stage runners
# ---------------------------------------------------------------------------


async def _run_schema_stage(
    *,
    path: Path,
    llm: LLMClient,
    output_path: Path,
    iterations: int,
    excludes: list[str] | None,
    result: PipelineResult,
) -> bool:
    """Run stage 1 (schema). Returns True if a schema file was produced."""
    try:
        state = await analyse_journey(
            path=path,
            llm=llm,
            output_path=output_path,
            iterations=iterations,
            excludes=excludes,
        )
    except Exception as e:
        result.outcomes.append(
            StageOutcome(
                stage=Stage.SCHEMA,
                status=StageStatus.FAILED,
                artifact=output_path if output_path.exists() else None,
                error=str(e),
            )
        )
        return False

    result.schema = state
    result.outcomes.append(
        StageOutcome(
            stage=Stage.SCHEMA,
            status=StageStatus.SUCCESS,
            artifact=output_path,
            summary=f"{len(state.tables)} table(s)",
        )
    )
    return True


async def _run_growth_stage(
    *,
    path: Path,
    llm: LLMClient,
    schema_path: Path,
    output_path: Path,
    excludes: list[str] | None,
    result: PipelineResult,
) -> bool:
    """Run stage 2 (growth manifest). Returns True on success."""
    try:
        state = await analyse_growth_from_schema(
            path=path,
            schema_path=schema_path,
            llm=llm,
            output_path=output_path,
            excludes=excludes,
        )
    except Exception as e:
        result.outcomes.append(
            StageOutcome(
                stage=Stage.GROWTH,
                status=StageStatus.FAILED,
                artifact=output_path if output_path.exists() else None,
                error=str(e),
            )
        )
        return False

    result.growth = state
    result.outcomes.append(
        StageOutcome(
            stage=Stage.GROWTH,
            status=StageStatus.SUCCESS,
            artifact=output_path,
            summary=(f"{len(state.features)} feature(s), {len(state.growth_opportunities)} opportunity(ies)"),
        )
    )
    return True


async def _run_plan_stage(
    *,
    path: Path,
    llm: LLMClient,
    manifest_path: Path,
    schema_path: Path,
    output_path: Path,
    new_features_path: Path,
    feature_count: int,
    result: PipelineResult,
) -> bool:
    """Run stage 3 (engine plan). Returns True on success."""
    try:
        state = await plan_engine_from_manifest(
            manifest_path=manifest_path,
            schema_path=schema_path,
            llm=llm,
            engine_path=output_path,
            new_features_path=new_features_path,
            project_root=path,
            feature_count=feature_count,
        )
    except Exception as e:
        result.outcomes.append(
            StageOutcome(
                stage=Stage.PLAN,
                status=StageStatus.FAILED,
                artifact=output_path if output_path.exists() else None,
                error=str(e),
            )
        )
        return False

    result.plan = state
    added = len(state.delta.features) if state.delta else 0
    result.outcomes.append(
        StageOutcome(
            stage=Stage.PLAN,
            status=StageStatus.SUCCESS,
            artifact=new_features_path,
            summary=f"{added} planned",
        )
    )
    return True


async def _run_journey_stage(
    *,
    path: Path,
    llm: LLMClient,
    schema_path: Path,
    manifest_path: Path,
    engine_path: Path,
    output_path: Path,
    result: PipelineResult,
) -> bool:
    """Run stage 4 (user-journey compiler). Returns True on success."""
    try:
        state = await compile_user_journey(
            schema_path=schema_path,
            manifest_path=manifest_path,
            engine_path=engine_path,
            output_path=output_path,
            llm=llm,
            project_root=path,
        )
    except Exception as e:
        result.outcomes.append(
            StageOutcome(
                stage=Stage.JOURNEY,
                status=StageStatus.FAILED,
                artifact=output_path if output_path.exists() else None,
                error=str(e),
            )
        )
        return False

    result.journey = state
    feature_count = len(state.compiled_features)
    subject_count = len(state.schema_analysis.get("ttv_journey_by_subject") or [])
    result.outcomes.append(
        StageOutcome(
            stage=Stage.JOURNEY,
            status=StageStatus.SUCCESS,
            artifact=output_path,
            summary=f"{feature_count} feature(s), {subject_count} subject journey(s)",
        )
    )
    return True


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


StageStartHook = Callable[[Stage, int, int], None]


async def run_pipeline(
    *,
    path: Path,
    llm: LLMClient,
    paths: PipelinePaths,
    stages: set[Stage],
    iterations: int = 6,
    excludes: list[str] | None = None,
    plan_feature_count: int = DEFAULT_FEATURE_COUNT,
    on_stage_start: StageStartHook | None = None,
) -> PipelineResult:
    """Run the requested subset of the journey pipeline.

    The pipeline stops early only when a required upstream artifact is missing
    (e.g. plan stage needs a manifest with growth opportunities). When the
    schema stage finds no tables, downstream stages run in their schemaless
    fallback paths rather than being skipped.

    Every outcome — success, skip, or failure — is recorded on the returned
    ``PipelineResult``; the function never raises for a stage-level failure.

    ``on_stage_start`` is invoked as ``(stage, index, total)`` immediately
    before each stage runs (not for skipped stages). CLIs use this to print
    stage headers.
    """
    result = PipelineResult()
    ordered: list[Stage] = [s for s in (Stage.SCHEMA, Stage.GROWTH, Stage.PLAN, Stage.JOURNEY) if s in stages]
    total = len(ordered)

    def _announce(stage: Stage) -> None:
        if on_stage_start is not None:
            on_stage_start(stage, ordered.index(stage) + 1, total)

    if Stage.SCHEMA in stages:
        _announce(Stage.SCHEMA)
        ok = await _run_schema_stage(
            path=path,
            llm=llm,
            output_path=paths.schema,
            iterations=iterations,
            excludes=excludes,
            result=result,
        )
        if not ok:
            return result

    if Stage.GROWTH in stages:
        _announce(Stage.GROWTH)
        if not paths.schema.exists():
            result.outcomes.append(
                StageOutcome(
                    stage=Stage.GROWTH,
                    status=StageStatus.SKIPPED,
                    summary=f"schema file not found: {paths.schema}",
                )
            )
        else:
            ok = await _run_growth_stage(
                path=path,
                llm=llm,
                schema_path=paths.schema,
                output_path=paths.growth,
                excludes=excludes,
                result=result,
            )
            if not ok:
                return result

    if Stage.PLAN in stages:
        _announce(Stage.PLAN)
        if not paths.growth.exists():
            result.outcomes.append(
                StageOutcome(
                    stage=Stage.PLAN,
                    status=StageStatus.SKIPPED,
                    summary=f"growth manifest not found: {paths.growth}",
                )
            )
            return result
        if result.growth is not None and not result.growth.growth_opportunities:
            result.outcomes.append(
                StageOutcome(
                    stage=Stage.PLAN,
                    status=StageStatus.SKIPPED,
                    summary="manifest has no growth_opportunities",
                )
            )
            return result

        await _run_plan_stage(
            path=path,
            llm=llm,
            manifest_path=paths.growth,
            schema_path=paths.schema,
            output_path=paths.engine,
            new_features_path=paths.new_features,
            feature_count=plan_feature_count,
            result=result,
        )

    if Stage.JOURNEY in stages:
        _announce(Stage.JOURNEY)
        missing = [
            ("schema", paths.schema),
            ("growth manifest", paths.growth),
            ("engine", paths.engine),
        ]
        absent = [(label, p) for label, p in missing if not p.exists()]
        if absent:
            labels = ", ".join(f"{label}: {p}" for label, p in absent)
            result.outcomes.append(
                StageOutcome(
                    stage=Stage.JOURNEY,
                    status=StageStatus.SKIPPED,
                    summary=f"upstream artifact(s) missing — {labels}",
                )
            )
            return result

        await _run_journey_stage(
            path=path,
            llm=llm,
            schema_path=paths.schema,
            manifest_path=paths.growth,
            engine_path=paths.engine,
            output_path=paths.journey,
            result=result,
        )

    return result
