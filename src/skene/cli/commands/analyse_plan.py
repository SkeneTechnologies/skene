"""Promote growth opportunities into concrete engine.yaml features."""

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
from skene.output_paths import DEFAULT_OUTPUT_DIR


@app.command(name="analyse-plan")
def analyse_plan_cmd(
    path: Path | None = typer.Argument(
        None,
        help="Path to codebase / project root (omit for current directory)",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    manifest: Path = typer.Option(
        Path(f"{DEFAULT_OUTPUT_DIR}/growth-manifest.json"),
        "-M",
        "--manifest",
        help="Path to growth-manifest.json (run 'analyse-growth-from-schema' first)",
    ),
    schema: Path = typer.Option(
        Path(f"{DEFAULT_OUTPUT_DIR}/schema.yaml"),
        "-s",
        "--schema",
        help="Path to schema.yaml (run 'analyse-journey' first to generate it)",
    ),
    output: Path = typer.Option(
        Path(f"{DEFAULT_OUTPUT_DIR}/engine.yaml"),
        "-o",
        "--output",
        help="Path to engine.yaml (read for context only; new-features.yaml is written beside it)",
    ),
    journey_output: Path | None = typer.Option(
        None,
        "--journey-output",
        help="Path for user-journey.yaml (default: next to engine.yaml)",
    ),
    skip_journey: bool = typer.Option(
        False,
        "--skip-journey",
        help="Stop after engine.yaml; do not compile user-journey.yaml",
    ),
    plan_count: int = typer.Option(
        DEFAULT_FEATURE_COUNT,
        "--plan-count",
        "-n",
        "--count",
        min=1,
        max=10,
        help="Number of growth features to promote from the manifest",
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
):
    """
    Promote growth opportunities from the manifest into concrete engine.yaml features.

    Reads the schema-driven growth manifest produced by
    ``analyse-growth-from-schema`` plus the introspected ``schema.yaml``, then
    asks the LLM to turn the top ``--plan-count`` (default 3) growth
    opportunities into fully-specified features — ``source``,
    ``subject_state_analysis`` and an optional ``action`` — and writes them
    to ``new-features.yaml`` beside ``engine.yaml``. The existing
    ``engine.yaml`` is read for context only and is never modified by this
    command; ``new-features.yaml`` is rewritten from scratch on every run.

    Examples:

        skene analyse-plan

        skene analyse-plan ./my-project -n 3

        skene analyse-plan --manifest ./skene-context/growth-manifest.json --schema ./skene-context/schema.yaml
    """
    base_path = resolve_base_path(path)

    schema_path = resolve_artifact_path(schema, "schema.yaml")
    if not schema_path.exists():
        error(f"Schema file not found: {schema_path}\nRun 'skene analyse-journey' first, or pass --schema <path>.")
        raise typer.Exit(1)

    manifest_path = resolve_artifact_path(manifest, "growth-manifest.json")
    if not manifest_path.exists():
        error(
            f"Growth manifest not found: {manifest_path}\n"
            "Run 'skene analyse-growth-from-schema' first, or pass --manifest <path>."
        )
        raise typer.Exit(1)

    engine_path = resolve_artifact_path(output, "engine.yaml")
    new_features_path = (manifest_path.parent / "new-features.yaml").resolve()
    journey_path = (
        resolve_artifact_path(journey_output, "user-journey.yaml")
        if journey_output is not None
        else (engine_path.parent / "user-journey.yaml").resolve()
    )

    rc = resolve_cli_config(
        api_key=api_key,
        provider=provider,
        model=model,
        base_url=base_url,
        quiet=quiet,
        debug=debug,
    )
    resolved_api_key = require_llm_credentials(rc, "analyse-plan")

    paths = PipelinePaths(
        schema=schema_path,
        growth=manifest_path,
        engine=engine_path,
        new_features=new_features_path,
        journey=journey_path,
    )
    stages: list[Stage] = [Stage.PLAN]
    if not skip_journey:
        stages.append(Stage.JOURNEY)

    render_kickoff_panel(
        title="skene · analyse-plan",
        base_path=base_path,
        rc=rc,
        extra_lines=[f"[bold]Features[/bold]  {plan_count}"],
    )

    execute_pipeline(
        base_path=base_path,
        rc=rc,
        api_key=resolved_api_key,
        paths=paths,
        stages=stages,
        iterations=0,
        excludes=None,
        plan_feature_count=plan_count,
        no_fallback=no_fallback,
    )
