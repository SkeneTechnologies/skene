"""Analyse the data schema of a codebase via iterative grep + LLM passes.

This is the entry point of the full journey pipeline:

    schema.yaml  →  growth-manifest.json  →  engine.yaml

Use ``--skip-growth`` or ``--skip-plan`` to stop early.
"""

from pathlib import Path

import typer

from skene.analyzers.plan_engine import DEFAULT_FEATURE_COUNT
from skene.cli._journey_runner import (
    PipelinePaths,
    Stage,
    execute_pipeline,
    render_kickoff_panel,
    require_llm_credentials,
    resolve_artifact_path,
    resolve_base_path,
    resolve_cli_config,
)
from skene.cli.app import app


@app.command(name="analyse-journey")
def analyse_journey_cmd(
    path: Path | None = typer.Argument(
        None,
        help="Path to codebase to analyse (omit for current directory)",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    output: Path = typer.Option(
        Path("./skene/schema.yaml"),
        "-o",
        "--output",
        help="Output path for schema.yaml",
    ),
    iterations: int = typer.Option(
        6,
        "--iterations",
        "-n",
        min=1,
        max=30,
        help="Number of grep + LLM refinement iterations",
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        envvar="SKENE_API_KEY",
        help="API key for LLM provider (or set SKENE_API_KEY env var)",
    ),
    provider: str | None = typer.Option(
        None,
        "--provider",
        "-p",
        help="LLM provider (openai, gemini, anthropic/claude, lmstudio, ollama, generic, skene)",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        "-m",
        help="LLM model name",
    ),
    base_url: str | None = typer.Option(
        None,
        "--base-url",
        envvar="SKENE_BASE_URL",
        help="Base URL for API endpoint",
    ),
    exclude: list[str] | None = typer.Option(
        None,
        "--exclude",
        "-e",
        help="Folder name to exclude from grep (repeatable)",
    ),
    quiet: bool = typer.Option(
        False,
        "-q",
        "--quiet",
        help="Suppress status messages; show only errors and final results",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Show diagnostic messages and log all LLM input/output",
    ),
    no_fallback: bool = typer.Option(
        False,
        "--no-fallback",
        help="Disable model fallback on rate limits; retry same model instead",
    ),
    skip_growth: bool = typer.Option(
        False,
        "--skip-growth",
        "--skip-growth-manifest",
        help="Stop after schema.yaml; do not derive a growth manifest",
    ),
    skip_plan: bool = typer.Option(
        False,
        "--skip-plan",
        help="Stop after the growth manifest; do not propose new-features.yaml",
    ),
    skip_journey: bool = typer.Option(
        False,
        "--skip-journey",
        help="Stop after new-features.yaml; do not compile user-journey.yaml",
    ),
    growth_output: Path | None = typer.Option(
        None,
        "--growth-output",
        help="Path for growth-manifest.json (default: next to schema)",
    ),
    plan_output: Path | None = typer.Option(
        None,
        "--plan-output",
        help="Path to engine.yaml (read for context only; default: next to schema)",
    ),
    new_features_output: Path | None = typer.Option(
        None,
        "--new-features-output",
        help="Path for new-features.yaml (default: same directory as growth manifest)",
    ),
    journey_output: Path | None = typer.Option(
        None,
        "--journey-output",
        help="Path for user-journey.yaml (default: next to schema)",
    ),
    plan_count: int = typer.Option(
        DEFAULT_FEATURE_COUNT,
        "--plan-count",
        min=1,
        max=10,
        help="Number of growth features to propose in new-features.yaml",
    ),
):
    """
    Analyse the data schema of a codebase, then optionally derive a growth
    manifest and propose growth opportunities as a fresh
    ``new-features.yaml`` (the existing ``engine.yaml`` is never modified).

    Repeatedly runs ripgrep for schema-related patterns — classes, models,
    tables, migrations, typed records — and asks the LLM to distil entities
    into a growing schema. Each iteration's response also suggests the next
    grep keyword, so the analysis journeys through the codebase until the
    schema stabilises.

    Examples:

        skene analyse-journey

        skene analyse-journey ./my-project -n 10 --skip-plan

        skene analyse-journey --provider anthropic --model claude-sonnet-4.6
    """
    base_path = resolve_base_path(path)
    rc = resolve_cli_config(
        api_key=api_key,
        provider=provider,
        model=model,
        base_url=base_url,
        quiet=quiet,
        debug=debug,
    )
    resolved_api_key = require_llm_credentials(rc, "analyse-journey")

    schema_path = resolve_artifact_path(output, "schema.yaml")
    growth_path = (
        resolve_artifact_path(growth_output, "growth-manifest.json")
        if growth_output is not None
        else schema_path.parent / "growth-manifest.json"
    )
    engine_path = (
        resolve_artifact_path(plan_output, "engine.yaml")
        if plan_output is not None
        else schema_path.parent / "engine.yaml"
    )
    new_features_path = (
        resolve_artifact_path(new_features_output, "new-features.yaml")
        if new_features_output is not None
        else (growth_path.parent / "new-features.yaml").resolve()
    )
    journey_path = (
        resolve_artifact_path(journey_output, "user-journey.yaml")
        if journey_output is not None
        else schema_path.parent / "user-journey.yaml"
    )

    stages: list[Stage] = [Stage.SCHEMA]
    if not skip_growth:
        stages.append(Stage.GROWTH)
    if not skip_growth and not skip_plan:
        stages.append(Stage.PLAN)
    if not skip_growth and not skip_plan and not skip_journey:
        stages.append(Stage.JOURNEY)

    render_kickoff_panel(
        title="skene · analyse-journey",
        base_path=base_path,
        rc=rc,
        extra_lines=[f"[bold]Iterations[/bold] {iterations}"],
    )

    execute_pipeline(
        base_path=base_path,
        rc=rc,
        api_key=resolved_api_key,
        paths=PipelinePaths(
            schema=schema_path,
            growth=growth_path,
            engine=engine_path,
            new_features=new_features_path,
            journey=journey_path,
        ),
        stages=stages,
        iterations=iterations,
        excludes=exclude if exclude else None,
        plan_feature_count=plan_count,
        no_fallback=no_fallback,
    )
