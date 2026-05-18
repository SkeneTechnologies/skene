"""Generate a journey.yaml from a repo's codebase and its SQL schema.

Replaces the legacy schema/growth/plan pipeline. Two LLM agents explore
in parallel — one over a directory of pre-exported SQL files, one over
the repo filesystem — and emit candidate milestones. The pipeline merges
them, classifies each into one of seven canonical lifecycle stages, and
assembles a validated Journey written to ``journey.yaml``.

See :mod:`skene.analyzers.journey.pipeline` for the algorithm.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.panel import Panel
from rich.table import Table

from skene.analyzers.journey.pipeline import (
    JourneyPipelineConfig,
    run_journey_pipeline,
)
from skene.analyzers.journey.serialize import write as write_journey
from skene.cli._journey_runner import (
    build_llm,
    require_llm_credentials,
    resolve_artifact_path,
    resolve_base_path,
    resolve_cli_config,
)
from skene.cli.app import app
from skene.output import console, error
from skene.output_paths import DEFAULT_OUTPUT_DIR


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
    schema_dir: Path | None = typer.Option(
        None,
        "--schema-dir",
        help=("Directory of pre-exported *.sql files for the schema agent. Required when no codebase path is given."),
    ),
    output: Path = typer.Option(
        Path(f"{DEFAULT_OUTPUT_DIR}/journey.yaml"),
        "-o",
        "--output",
        help="Output path for journey.yaml",
    ),
    product_name: str | None = typer.Option(
        None,
        "--product-name",
        help="Product name in the output (default: inferred from the repo directory name)",
    ),
    schema_max_turns: int = typer.Option(
        150,
        "--schema-max-turns",
        min=1,
        max=500,
        help="Maximum agent turns for the schema agent",
    ),
    code_max_turns: int = typer.Option(
        200,
        "--code-max-turns",
        min=1,
        max=500,
        help="Maximum agent turns for the code agent",
    ),
    classify_concurrency: int = typer.Option(
        8,
        "--classify-concurrency",
        min=1,
        max=64,
        help="Parallel classifier requests",
    ),
    no_specialize: bool = typer.Option(
        False,
        "--no-specialize",
        help="Skip stage specialization; use canonical stage vocabulary",
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
) -> None:
    """
    Generate a journey.yaml describing the user lifecycle of the target product.

    Provide a codebase path, a ``--schema-dir`` of *.sql files, or both. The
    pipeline runs two parallel agents:

    \b
      - Schema agent: walks the parsed SQL schema and emits a milestone for
        every user-facing table.
      - Code agent: walks the repo and emits a milestone for every
        user-facing route, handler, analytics call, or job.

    The candidates are merged, classified into discovery / onboarding /
    activation / engagement / retention / expansion / virality, and
    assembled into a single validated Journey document.

    Examples:

    \b
        skene analyse-journey ./my-app --schema-dir ./supabase-schemas
        skene analyse-journey --schema-dir ./schemas -o journey.json
        skene analyse-journey ./my-app  # code-only mode (no SQL)
    """
    # At least one input is required.
    if path is None and schema_dir is None:
        error("at least one of PATH or --schema-dir is required")
        raise typer.Exit(2)

    base_path = resolve_base_path(path) if path is not None else None
    schema_path = schema_dir.resolve() if schema_dir is not None else None
    if schema_path is not None:
        if not schema_path.exists():
            error(f"--schema-dir does not exist: {schema_path}")
            raise typer.Exit(1)
        if not schema_path.is_dir():
            error(f"--schema-dir is not a directory: {schema_path}")
            raise typer.Exit(1)

    # Config resolution needs a project root; fall back to cwd if only --schema-dir is given.
    config_root = base_path if base_path is not None else Path.cwd()
    rc = resolve_cli_config(
        project_root=config_root,
        api_key=api_key,
        provider=provider,
        model=model,
        base_url=base_url,
        quiet=quiet,
        debug=debug,
    )
    resolved_api_key = require_llm_credentials(rc, "analyse-journey")

    journey_path = resolve_artifact_path(output, "journey.yaml")
    journey_path.parent.mkdir(parents=True, exist_ok=True)

    resolved_product_name = product_name or _infer_product_name(base_path, schema_path)

    cfg = JourneyPipelineConfig(
        repo_root=base_path,
        schema_dir=schema_path,
        product_name=resolved_product_name,
        classify_concurrency=classify_concurrency,
        schema_max_turns=schema_max_turns,
        code_max_turns=code_max_turns,
        specialize=not no_specialize,
    )

    _render_kickoff(
        title="skene · analyse-journey",
        base_path=base_path,
        schema_dir=schema_path,
        rc=rc,
        product_name=resolved_product_name,
        journey_path=journey_path,
        specialize=cfg.specialize,
    )

    llm = build_llm(rc, resolved_api_key, no_fallback=no_fallback)

    import asyncio

    try:
        journey = asyncio.run(run_journey_pipeline(cfg, llm))
    except Exception as e:  # noqa: BLE001 — surface any failure to the user
        error(f"pipeline failed: {e}")
        raise typer.Exit(1) from e

    write_journey(journey, journey_path)

    _render_summary(journey_path, journey)


def _infer_product_name(repo_root: Path | None, schema_dir: Path | None) -> str:
    if repo_root is not None:
        return repo_root.name or "Product"
    if schema_dir is not None:
        return schema_dir.parent.name or schema_dir.name or "Product"
    return "Product"


def _render_kickoff(
    *,
    title: str,
    base_path: Path | None,
    schema_dir: Path | None,
    rc,
    product_name: str,
    journey_path: Path,
    specialize: bool,
) -> None:
    lines = [
        f"[bold]Product[/bold]    {product_name}",
        f"[bold]Repo[/bold]       {base_path or '[dim](none)[/dim]'}",
        f"[bold]Schema[/bold]     {schema_dir or '[dim](none)[/dim]'}",
        f"[bold]Output[/bold]     {journey_path}",
        f"[bold]Provider[/bold]   {rc.provider} · [dim]{rc.model}[/dim]",
        f"[bold]Specialize[/bold] {'yes' if specialize else 'no'}",
    ]
    console.print(Panel.fit("\n".join(lines), title=title, border_style="blue"))


def _render_summary(journey_path: Path, journey) -> None:
    table = Table(title="Journey summary", title_style="bold", show_lines=False)
    table.add_column("Stage", style="bold")
    table.add_column("Milestones", justify="right")
    for stage in journey.stages:
        table.add_row(f"{stage.id} ({stage.name})", str(len(stage.milestones)))
    table.add_row("[dim]total[/dim]", str(sum(len(s.milestones) for s in journey.stages)))
    console.print()
    console.print(table)
    console.print(f"\n[green]✓[/green] wrote {journey_path}")
