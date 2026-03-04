"""
Upstream authentication for skene push.

Login stores connection info (URL, workspace) per-project in .skene-upstream
and saves the token securely in ~/.config/skene-growth/credentials keyed
by workspace slug.
"""

import getpass
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from skene_growth.config import (
    load_config,
    load_project_upstream,
    load_toml,
    remove_project_upstream,
    remove_workspace_token,
    resolve_workspace_token,
    save_project_upstream,
    save_workspace_token,
)
from skene_growth.growth_loops.upstream import _api_base_from_upstream, _workspace_slug_from_url, validate_token

console = Console()


def _upstream_from_project_config() -> str | None:
    """Read upstream URL from .skene-growth.config. Checks cwd first, then parents."""
    for path in [Path.cwd() / ".skene-growth.config", *[p / ".skene-growth.config" for p in Path.cwd().parents]]:
        if path.exists():
            try:
                data = load_toml(path)
                val = data.get("upstream") or data.get("upstream_url")
                if isinstance(val, str) and val.strip():
                    return val.strip()
            except Exception:
                pass
    return None


def _api_key_from_project_config() -> str | None:
    """Read upstream_api_key from .skene-growth.config. Checks cwd first, then parents."""
    for path in [Path.cwd() / ".skene-growth.config", *[p / ".skene-growth.config" for p in Path.cwd().parents]]:
        if path.exists():
            try:
                data = load_toml(path)
                val = data.get("upstream_api_key")
                if isinstance(val, str) and val.strip():
                    return val.strip()
            except Exception:
                pass
    return None


def cmd_login(upstream_url: str | None = None) -> None:
    """
    Interactive login for upstream push.

    Validates the token via GET /me, saves connection info to .skene-upstream
    and the token to ~/.config/skene-growth/credentials.
    Uses upstream and upstream_api_key from config as backup when logged out.
    """
    config = load_config()
    project = load_project_upstream()

    url = (
        upstream_url
        or (project.get("upstream") if project else None)
        or config.upstream
        or _upstream_from_project_config()
    )
    if not url:
        cwd_config = Path.cwd() / ".skene-growth.config"
        hint = ""
        if cwd_config.exists():
            hint = f"\n[dim]Found {cwd_config} but no 'upstream' key. Add:\n  upstream = \"http://localhost:3000/workspace/your-workspace\"[/dim]"
        else:
            hint = f"\n[dim]No .skene-growth.config in {Path.cwd()} or parent dirs.[/dim]"
        console.print(
            "[red]Error:[/red] No upstream URL provided.\n"
            "Pass via --upstream or add to .skene-growth.config:\n"
            '  upstream = "https://skene.ai/workspace/your-workspace"' + hint
        )
        raise typer.Exit(1)

    api_base = _api_base_from_upstream(url)
    workspace = _workspace_slug_from_url(url)

    # Use API key from config as backup when logged out (no .skene-upstream)
    token = None
    config_api_key = config.upstream_api_key or _api_key_from_project_config()
    if not project and config_api_key:
        config_api_key = config_api_key.strip()
        if config_api_key and validate_token(api_base, config_api_key):
            token = config_api_key
            console.print("[green]Using API key from config.[/green]")

    if not token:
        console.print("----------------------------------------------------------------")
        console.print(
            f"[dim]Logging in to workspace:[/dim] [bold]{workspace}[/bold]  ({url})"
        )
        base = url.rstrip("/").split("/workspace/")[0] if "/workspace/" in url else url.rstrip("/")
        api_key_url = f"{base}/workspace/{workspace}/apikeys?setting_open=true"
        console.print("You need Skene API key. Get it at:")
        console.print(f"{api_key_url}")
        token = getpass.getpass("Paste your upstream API Key: ")
        if not token or not token.strip():
            console.print("[red]No API key provided. Login cancelled.[/red]")
            raise typer.Exit(1)
        if not validate_token(api_base, token.strip()):
            console.print("[red]Invalid API key or connection failed.[/red]")
            raise typer.Exit(1)
        token = token.strip()

    save_project_upstream(url, workspace)
    cred_path = save_workspace_token(workspace, token)
    console.print(
        f"[green]Logged in to [bold]{workspace}[/bold].[/green]\n"
        f"  Connection: .skene-upstream\n"
        f"  Token:      {cred_path}"
    )


def cmd_logout() -> None:
    """Remove project .skene-upstream and the workspace token from credentials."""
    project = load_project_upstream()
    if project and project.get("workspace"):
        remove_workspace_token(project["workspace"])

    removed = remove_project_upstream()
    if removed:
        console.print(f"[green]Logged out.[/green] Removed {removed}")
    else:
        console.print("[dim]No project upstream credentials found (.skene-upstream).[/dim]")


def cmd_login_status() -> None:
    """Show current upstream login status for this project."""
    project = load_project_upstream()

    if not project:
        console.print("[yellow]Not logged in.[/yellow]  No .skene-upstream found in this project.")
        console.print("[dim]Run: skene login --upstream https://skene.ai/workspace/your-workspace[/dim]")
        return

    workspace = project.get("workspace", "")
    token = resolve_workspace_token(workspace) if workspace else None

    table = Table(title="Upstream Login Status", show_header=False, padding=(0, 2))
    table.add_column("Key", style="bold")
    table.add_column("Value")

    table.add_row("Upstream", project.get("upstream", "[dim]?[/dim]"))
    table.add_row("Workspace", workspace or "[dim]?[/dim]")

    if token:
        masked = token[:4] + "..." + token[-4:] if len(token) > 12 else "****"
        table.add_row("Token", masked)
    else:
        table.add_row("Token", "[red]Missing — run skene login[/red]")

    table.add_row("Logged in at", project.get("logged_in_at", "[dim]?[/dim]"))

    from skene_growth.config import find_project_upstream_file, get_credentials_path

    path = find_project_upstream_file()
    if path:
        table.add_row("Connection file", str(path))
    table.add_row("Credentials file", str(get_credentials_path()))

    console.print(table)
