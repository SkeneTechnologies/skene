"""Validate a growth-manifest.json against the schema."""

import json
from pathlib import Path

import typer
from rich.table import Table

from skene.cli.app import app
from skene.output import console, error, success
from skene.output import status as output_status


@app.command(rich_help_panel="manage")
def validate(
    manifest: Path = typer.Argument(
        ...,
        help="Path to growth-manifest.json to validate",
        exists=True,
    ),
):
    """
    Validate a growth-manifest.json against the schema.

    Checks that the manifest file is valid JSON and conforms
    to the GrowthManifest schema.

    Examples:

        uvx skene validate ./growth-manifest.json
        # Or: uvx skene validate ./growth-manifest.json
    """
    output_status(f"Validating: {manifest}")

    try:
        # Load JSON
        data = json.loads(manifest.read_text())

        # Validate against schema
        from skene.manifest import GrowthManifest

        manifest_obj = GrowthManifest(**data)

        success("Manifest conforms to schema.")

        # Show summary
        table = Table(title="Manifest Summary")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Project", manifest_obj.project_name)
        table.add_row("Version", manifest_obj.version)
        table.add_row("Tech Stack", manifest_obj.tech_stack.language or "Unknown")
        table.add_row("Current Growth Features", str(len(manifest_obj.current_growth_features)))
        table.add_row("New Growth Opportunities", str(len(manifest_obj.growth_opportunities)))

        console.print(table)

    except json.JSONDecodeError as e:
        error(f"Invalid JSON: {e}")
        raise typer.Exit(1)
    except Exception as e:
        error(f"Validation failed: {e}")
        raise typer.Exit(1)
