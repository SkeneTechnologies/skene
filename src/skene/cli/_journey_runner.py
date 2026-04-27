"""
Shared CLI plumbing for the journey pipeline (schema → growth → plan).

Centralises what used to be copy-pasted across ``analyse_journey.py``,
``analyse_growth_from_schema.py`` and ``analyse_plan.py``:

- artifact path resolution (handles dir-as-arg, absolute vs relative, missing suffix)
- LLM client construction from a ``ResolvedConfig``
- kickoff panel rendering (stage plan)
- final summary rendering (artifact table)
- the ``asyncio.run`` call and typer exit handling
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from pydantic import SecretStr
from rich.panel import Panel
from rich.table import Table

from skene.analyzers.pipeline import (
    PipelinePaths,
    PipelineResult,
    Stage,
    StageOutcome,
    StageStatus,
    run_pipeline,
)
from skene.cli.app import ResolvedConfig, resolve_cli_config
from skene.llm import create_llm_client
from skene.output import console, error

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def resolve_artifact_path(p: Path, default_filename: str) -> Path:
    """Normalise a CLI-supplied output path.

    - relative paths become absolute against ``Path.cwd()``
    - a path that points at an existing directory gets ``default_filename`` appended
    - a path without a file suffix is treated as a directory and gets
      ``default_filename`` appended
    - everything else is resolved as-is
    """
    resolved = p if p.is_absolute() else (Path.cwd() / p).resolve()
    if resolved.exists() and resolved.is_dir():
        return (resolved / default_filename).resolve()
    if not resolved.suffix:
        return (resolved / default_filename).resolve()
    return resolved.resolve()


def resolve_base_path(path: Path | None) -> Path:
    """Resolve the project root path and validate it is an existing directory."""
    base_path = (path if path is not None else Path(".")).resolve()
    if not base_path.exists():
        error(f"Path does not exist: {base_path}")
        raise typer.Exit(1)
    if not base_path.is_dir():
        error(f"Path is not a directory: {base_path}")
        raise typer.Exit(1)
    return base_path


# ---------------------------------------------------------------------------
# LLM client
# ---------------------------------------------------------------------------


def require_llm_credentials(rc: ResolvedConfig, command_name: str) -> str:
    """Validate rc has credentials for the LLM call; return an effective API key.

    Local providers (lmstudio/ollama/generic) don't need a real key — we fall
    back to the provider name so downstream code has a non-empty string to
    pass around.
    """
    if not rc.api_key and not rc.is_local:
        error(
            f"An API key is required for {command_name}. "
            "Set --api-key, SKENE_API_KEY env var, or add api_key to .skene.config."
        )
        raise typer.Exit(1)
    return rc.api_key or rc.provider


def build_llm(rc: ResolvedConfig, api_key: str, *, no_fallback: bool):
    """Construct an LLMClient from a resolved config."""
    return create_llm_client(
        rc.provider,
        SecretStr(api_key),
        rc.model,
        base_url=rc.base_url,
        debug=rc.debug,
        no_fallback=no_fallback,
    )


# ---------------------------------------------------------------------------
# Kickoff + summary rendering
# ---------------------------------------------------------------------------

_STAGE_LABEL = {
    Stage.SCHEMA: "Schema discovery",
    Stage.GROWTH: "Growth manifest",
    Stage.PLAN: "Engine plan",
    Stage.JOURNEY: "User journey",
}

_STATUS_STYLE = {
    StageStatus.SUCCESS: ("[green]✓[/green]", "green"),
    StageStatus.SKIPPED: ("[yellow]○[/yellow]", "yellow"),
    StageStatus.FAILED: ("[red]✗[/red]", "red"),
}


def render_kickoff_panel(
    *,
    title: str,
    base_path: Path,
    rc: ResolvedConfig,
    extra_lines: list[str] | None = None,
) -> None:
    """Render a short kickoff panel before any work starts (path + provider)."""
    lines = [
        f"[bold]Path[/bold]      {base_path}",
        f"[bold]Provider[/bold]  {rc.provider} · [dim]{rc.model}[/dim]",
    ]
    if extra_lines:
        lines.extend(extra_lines)

    console.print(Panel.fit("\n".join(lines), title=title, border_style="blue"))


def render_stage_header(stage: Stage, index: int, total: int) -> None:
    """Print a visual separator before a stage starts."""
    label = _STAGE_LABEL[stage]
    console.print(f"\n[bold blue]── [{index}/{total}] {label} ──[/bold blue]\n")


def render_summary(result: PipelineResult) -> None:
    """Render the final artifact table across all stages."""
    table = Table(title="Pipeline summary", title_style="bold", show_lines=False)
    table.add_column("", width=2)
    table.add_column("Stage", style="bold")
    table.add_column("Result")
    table.add_column("Artifact", overflow="fold")

    for outcome in result.outcomes:
        icon, colour = _STATUS_STYLE[outcome.status]
        detail = outcome.summary or ""
        if outcome.status is StageStatus.FAILED and outcome.error:
            detail = f"{detail} — {outcome.error}" if detail else outcome.error
        artifact = str(outcome.artifact) if outcome.artifact else "—"
        table.add_row(
            icon,
            _STAGE_LABEL[outcome.stage],
            f"[{colour}]{outcome.status.value}[/{colour}]   {detail}".strip(),
            artifact,
        )

    console.print()
    console.print(table)


# ---------------------------------------------------------------------------
# Orchestration helper
# ---------------------------------------------------------------------------


def execute_pipeline(
    *,
    base_path: Path,
    rc: ResolvedConfig,
    api_key: str,
    paths: PipelinePaths,
    stages: list[Stage],
    iterations: int,
    excludes: list[str] | None,
    plan_feature_count: int,
    no_fallback: bool,
) -> PipelineResult:
    """Run the pipeline, render a summary, exit non-zero on failure."""
    requested = set(stages)

    async def _go() -> PipelineResult:
        llm = build_llm(rc, api_key, no_fallback=no_fallback)
        return await run_pipeline(
            path=base_path,
            llm=llm,
            paths=paths,
            stages=requested,
            iterations=iterations,
            excludes=excludes,
            plan_feature_count=plan_feature_count,
            on_stage_start=render_stage_header,
        )

    result = asyncio.run(_go())
    render_summary(result)
    if result.failed:
        raise typer.Exit(1)
    return result


# Re-export for convenience so commands only import from this module.
__all__ = [
    "PipelinePaths",
    "PipelineResult",
    "ResolvedConfig",
    "Stage",
    "StageOutcome",
    "StageStatus",
    "build_llm",
    "execute_pipeline",
    "render_kickoff_panel",
    "render_stage_header",
    "render_summary",
    "require_llm_credentials",
    "resolve_artifact_path",
    "resolve_base_path",
    "resolve_cli_config",
]
