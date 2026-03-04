"""CLI commands for growth feature registry."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from skene_growth.feature_registry import (
    FEATURE_REGISTRY_FILENAME,
    export_registry_to_format,
    load_feature_registry,
)

console = Console()

features_app = typer.Typer(help="Manage growth feature registry.")


@features_app.command("export")
def cmd_export(
    context_dir: Optional[Path] = typer.Option(
        None,
        "--context",
        "-c",
        help="Path to skene-context directory (auto-detected if omitted)",
    ),
    path: Path = typer.Argument(
        ".",
        help="Project root (to locate skene-context)",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Output format: json, csv, markdown",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "-o",
        "--output",
        help="Output path (stdout if omitted)",
    ),
):
    """
    Export the feature registry for use in other tools.

    Reads skene-context/growth-features.json and outputs in the requested format.
    Use for docs, dashboards, planning integrations (Linear, Notion, etc.).
    """
    base_dir = context_dir if context_dir else path / "skene-context"
    if not base_dir.exists():
        base_dir = path
    registry_path = base_dir / FEATURE_REGISTRY_FILENAME
    registry = load_feature_registry(registry_path)

    if not registry or not registry.get("features"):
        console.print(
            "[yellow]No feature registry found or registry is empty.[/yellow]\n"
            f"Run [cyan]skene analyze[/cyan] first to populate {registry_path}"
        )
        raise typer.Exit(1)

    try:
        out = export_registry_to_format(registry, format)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(out, encoding="utf-8")
        console.print(f"[green]Exported to[/green] {output}")
    else:
        console.print(out)
