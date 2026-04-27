"""Compile user-journey.yaml from existing schema, manifest, and engine artifacts."""

from pathlib import Path

import typer

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


@app.command(name="analyse-user-journey")
def analyse_user_journey_cmd(
    path: Path | None = typer.Argument(
        None,
        help="Path to codebase / project root (omit for current directory)",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    schema: Path = typer.Option(
        Path("./skene/schema.yaml"),
        "-s",
        "--schema",
        help="Path to schema.yaml (run 'analyse-journey' first)",
    ),
    manifest: Path = typer.Option(
        Path("./skene/growth-manifest.json"),
        "-M",
        "--manifest",
        help="Path to growth-manifest.json (run 'analyse-growth-from-schema' first)",
    ),
    engine: Path = typer.Option(
        Path("./skene/engine.yaml"),
        "-e",
        "--engine",
        help="Path to engine.yaml (run 'analyse-plan' first)",
    ),
    output: Path | None = typer.Option(
        None,
        "-o",
        "--output",
        help="Output path for user-journey.yaml (default: next to engine.yaml)",
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
    Compile ``user-journey.yaml`` from existing schema, growth manifest, and
    engine.yaml — without re-running the upstream pipeline stages.

    Useful for re-generating the journey artifact when the engine or schema
    has changed but the upstream LLM passes are still fresh.

    Examples:

        skene analyse-user-journey

        skene analyse-user-journey ./my-project
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

    engine_path = resolve_artifact_path(engine, "engine.yaml")
    if not engine_path.exists():
        error(f"Engine file not found: {engine_path}\nRun 'skene analyse-plan' first, or pass --engine <path>.")
        raise typer.Exit(1)

    journey_path = (
        resolve_artifact_path(output, "user-journey.yaml")
        if output is not None
        else (engine_path.parent / "user-journey.yaml").resolve()
    )
    new_features_path = (engine_path.parent / "new-features.yaml").resolve()

    rc = resolve_cli_config(
        api_key=api_key,
        provider=provider,
        model=model,
        base_url=base_url,
        quiet=quiet,
        debug=debug,
    )
    resolved_api_key = require_llm_credentials(rc, "analyse-user-journey")

    paths = PipelinePaths(
        schema=schema_path,
        growth=manifest_path,
        engine=engine_path,
        new_features=new_features_path,
        journey=journey_path,
    )
    render_kickoff_panel(
        title="skene · analyse-user-journey",
        base_path=base_path,
        rc=rc,
    )

    execute_pipeline(
        base_path=base_path,
        rc=rc,
        api_key=resolved_api_key,
        paths=paths,
        stages=[Stage.JOURNEY],
        iterations=0,
        excludes=None,
        plan_feature_count=0,
        no_fallback=no_fallback,
    )
