"""Derive a growth manifest from an existing schema + codebase evidence."""

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
from skene.output import error


@app.command(name="analyse-growth-from-schema")
def analyse_growth_from_schema_cmd(
    path: Path | None = typer.Argument(
        None,
        help="Path to codebase to analyse (omit for current directory)",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    schema: Path = typer.Option(
        Path("./skene/schema.yaml"),
        "-s",
        "--schema",
        help="Path to schema.yaml (run 'analyse-journey' first to generate it)",
    ),
    output: Path = typer.Option(
        Path("./skene/growth-manifest.json"),
        "-o",
        "--output",
        help="Output path for growth-manifest.json",
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
    skip_plan: bool = typer.Option(
        False,
        "--skip-plan",
        help="Stop after the growth manifest; do not write engine.yaml",
    ),
    plan_output: Path | None = typer.Option(
        None,
        "--plan-output",
        help="Path for engine.yaml (default: next to schema)",
    ),
    plan_count: int = typer.Option(
        DEFAULT_FEATURE_COUNT,
        "--plan-count",
        min=1,
        max=10,
        help="Number of growth features to promote into engine.yaml",
    ),
):
    """
    Derive a growth manifest from the already-built schema plus codebase evidence.

    Uses the tables, columns, and relationships in ``schema.yaml`` to hypothesise
    which growth features (invites, subscriptions, onboarding, analytics, etc.)
    the product supports, then searches the codebase with ripgrep for grounded
    evidence and assembles a standard ``growth-manifest.json``. Unless
    ``--skip-plan`` is set, ``analyse-plan`` runs immediately afterward.

    Examples:

        skene analyse-growth-from-schema

        skene analyse-growth-from-schema ./my-project -s ./skene/schema.yaml

        skene analyse-growth-from-schema --provider anthropic --model claude-sonnet-4.6
    """
    base_path = resolve_base_path(path)

    schema_path = resolve_artifact_path(schema, "schema.yaml")
    if not schema_path.exists():
        error(f"Schema file not found: {schema_path}\nRun 'skene analyse-journey' first, or pass --schema <path>.")
        raise typer.Exit(1)

    growth_path = resolve_artifact_path(output, "growth-manifest.json")
    engine_path = (
        resolve_artifact_path(plan_output, "engine.yaml")
        if plan_output is not None
        else schema_path.parent / "engine.yaml"
    )

    rc = resolve_cli_config(
        api_key=api_key,
        provider=provider,
        model=model,
        base_url=base_url,
        quiet=quiet,
        debug=debug,
    )
    resolved_api_key = require_llm_credentials(rc, "analyse-growth-from-schema")

    stages: list[Stage] = [Stage.GROWTH]
    if not skip_plan:
        stages.append(Stage.PLAN)

    new_features_path = (growth_path.parent / "new-features.yaml").resolve()
    journey_path = (engine_path.parent / "user-journey.yaml").resolve()
    paths = PipelinePaths(
        schema=schema_path,
        growth=growth_path,
        engine=engine_path,
        new_features=new_features_path,
        journey=journey_path,
    )
    render_kickoff_panel(
        title="skene · analyse-growth-from-schema",
        base_path=base_path,
        rc=rc,
    )

    execute_pipeline(
        base_path=base_path,
        rc=rc,
        api_key=resolved_api_key,
        paths=paths,
        stages=stages,
        iterations=0,
        excludes=exclude if exclude else None,
        plan_feature_count=plan_count,
        no_fallback=no_fallback,
    )
