"""Manage skene configuration."""

from pathlib import Path

import typer
from rich.prompt import Confirm

from skene.cli.app import app
from skene.cli.config_manager import (
    create_sample_config,
    interactive_config_setup,
    save_config,
    show_config_status,
)
from skene.output import console, error


@app.command(rich_help_panel="manage")
def config(
    init: bool = typer.Option(
        False,
        "--init",
        help="Create a sample config file in current directory",
    ),
    show: bool = typer.Option(
        False,
        "--show",
        help="Show current configuration values",
    ),
):
    """
    Manage skene configuration.

    Configuration files are loaded in this order (later overrides earlier):
    1. User config: ~/.config/skene/config
    2. Project config: ./.skene.config
    3. Environment variables (SKENE_API_KEY, SKENE_PROVIDER)
    4. CLI arguments

    Examples:

        # Show current configuration
        uvx skene config --show
        # Or: uvx skene config --show

        # Create a sample config file
        uvx skene config --init
        # Or: uvx skene config --init
    """
    from skene.config import find_project_config, find_user_config, load_config

    # NOTE: config command uses console.print throughout (not output functions)
    # because it's an interactive TUI — formatted display, prompts, and wizard output.
    if init:
        config_path = Path(".skene.config")
        if config_path.exists():
            console.print(f"[yellow]Config already exists:[/yellow] {config_path}")
            raise typer.Exit(1)

        create_sample_config(config_path)
        console.print(f"[green]Created config file:[/green] {config_path}")
        console.print("\nEdit this file to add your API key and customize settings.")
        return

    # Default: show configuration
    cfg = load_config()
    project_cfg = find_project_config()
    user_cfg = find_user_config()

    show_config_status(cfg, project_cfg, user_cfg)

    if not project_cfg and not user_cfg:
        console.print("\n[dim]Tip: Run 'skene config --init' to create a config file[/dim]")
        return

    # Ask if user wants to edit
    console.print()
    edit = Confirm.ask("[bold yellow]Do you want to edit this configuration?[/bold yellow]", default=False)

    if not edit:
        return

    # Interactive configuration setup
    config_path, selected_provider, selected_model, new_api_key, base_url = interactive_config_setup()

    # Save configuration
    try:
        save_config(config_path, selected_provider, selected_model, new_api_key, base_url)
        console.print(f"\n[green]✓ Configuration saved to:[/green] {config_path}")
        console.print(f"[green]  Provider:[/green] {selected_provider}")
        console.print(f"[green]  Model:[/green] {selected_model}")
        if base_url:
            console.print(f"[green]  Base URL:[/green] {base_url}")
        console.print(f"[green]  API Key:[/green] {'Set' if new_api_key else 'Not set'}")
    except Exception as e:
        error(f"Error saving configuration: {e}")
        raise typer.Exit(1)
