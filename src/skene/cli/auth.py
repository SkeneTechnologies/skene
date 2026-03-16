"""
Upstream authentication for skene push.

Login stores connection info (URL, workspace, API key) in .skene.config.
Logout removes those fields from the same file.
"""

import getpass
from pathlib import Path

import typer
from rich.table import Table

from skene.config import (
    find_project_config,
    load_config,
    remove_upstream_from_config,
    resolve_upstream_api_key_with_source,
    save_upstream_to_config,
)
from skene.growth_loops.upstream import _api_base_from_upstream, _workspace_slug_from_url, validate_token
from skene.output import console
from skene.output import error as output_error
from skene.output import status as output_status
from skene.output import success as output_success
from skene.output import warning as output_warning


def cmd_login(upstream_url: str | None = None) -> None:
    """
    Interactive login for upstream push.

    Validates the token via GET /me, saves connection info to .skene.config.
    """
    config = load_config()

    url = upstream_url or config.upstream
    if not url:
        cwd_config = Path.cwd() / ".skene.config"
        hint = ""
        if cwd_config.exists():
            hint = f"\n[dim]Found {cwd_config} but no 'upstream' key.[/dim]"
        else:
            hint = f"\n[dim]No .skene.config in {Path.cwd()} or parent dirs.[/dim]"

        console.print(hint)
        output_error(
            "No upstream URL provided.\n"
            "Pass via --upstream or add to .skene.config:\n"
            '  upstream = "https://skene.ai/workspace/your-workspace"'
        )
        raise typer.Exit(1)

    api_base = _api_base_from_upstream(url)
    workspace = _workspace_slug_from_url(url)

    token = None
    config_api_key = config.upstream_api_key
    if config_api_key:
        config_api_key = config_api_key.strip()
        if config_api_key and validate_token(api_base, config_api_key):
            token = config_api_key
            output_success("Using API key from config.")

    if not token:
        console.print("----------------------------------------------------------------")
        console.print(f"[dim]Logging in to workspace:[/dim] [bold]{workspace}[/bold]  ({url})")
        base = url.rstrip("/").split("/workspace/")[0] if "/workspace/" in url else url.rstrip("/")
        api_key_url = f"{base}/workspace/{workspace}/apikeys"
        console.print("You need Skene API key. Get it at:")
        console.print(f"{api_key_url}")
        token = getpass.getpass("Paste your upstream API Key: ")
        if not token or not token.strip():
            output_error("No API key provided. Login cancelled.")
            raise typer.Exit(1)
        if not validate_token(api_base, token.strip()):
            output_error("Invalid API key or connection failed.")
            raise typer.Exit(1)
        token = token.strip()

    config_path = save_upstream_to_config(url, workspace, token)
    output_success(f"Logged in to {workspace}.\n  Config: {config_path}")


def cmd_logout() -> None:
    """Remove upstream credentials from .skene.config."""
    removed = remove_upstream_from_config()
    if removed:
        output_success(f"Logged out. Removed upstream credentials from {removed}")
    else:
        output_status("No upstream credentials found in .skene.config.")


def cmd_login_status() -> None:
    """Show current upstream login status from .skene.config."""
    config = load_config()
    upstream = config.upstream
    workspace = config.get("workspace", "")

    if not upstream:
        output_warning("Not logged in.  No upstream in .skene.config.")
        output_status("Run: skene login --upstream https://skene.ai/workspace/your-workspace")
        return

    api_key, api_key_source = resolve_upstream_api_key_with_source(config)

    table = Table(title="Upstream Login Status", show_header=False, padding=(0, 2))
    table.add_column("Key", style="bold")
    table.add_column("Value")

    table.add_row("Upstream", upstream)
    table.add_row("Workspace", workspace or "[dim]?[/dim]")

    if api_key:
        masked = api_key[:4] + "..." + api_key[-4:] if len(api_key) > 12 else "****"
        table.add_row("API Key", f"{masked}  [dim](source: {api_key_source})[/dim]")
    else:
        table.add_row("API Key", "[red]Missing — run skene login[/red]")

    config_path = find_project_config()
    if config_path:
        table.add_row("Config file", str(config_path))

    console.print(table)
