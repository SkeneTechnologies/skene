"""
Upstream authentication for skene deploy push.

Login stores connection info (URL, workspace) per-project in .skene-upstream
and saves the token securely in ~/.config/skene-growth/credentials keyed
by workspace slug.
"""

import getpass

import typer
from rich.console import Console
from rich.table import Table

from skene_growth.config import (
    load_config,
    load_project_upstream,
    remove_project_upstream,
    remove_workspace_token,
    resolve_workspace_token,
    save_project_upstream,
    save_workspace_token,
)
from skene_growth.growth_loops.upstream import _api_base_from_upstream, _workspace_slug_from_url, validate_token

console = Console()


def cmd_login(upstream_url: str | None = None) -> None:
    """
    Interactive login for upstream push.

    Validates the token via GET /me, saves connection info to .skene-upstream
    and the token to ~/.config/skene-growth/credentials.
    """
    config = load_config()
    project = load_project_upstream()

    url = upstream_url or (project.get("upstream") if project else None) or config.upstream
    if not url:
        console.print(
            "[red]Error:[/red] No upstream URL provided.\n"
            "Pass via --upstream or add to .skene-growth.config:\n"
            '  upstream = "https://skene.ai/workspace/your-workspace"'
        )
        raise typer.Exit(1)

    api_base = _api_base_from_upstream(url)
    workspace = _workspace_slug_from_url(url)
    console.print(
        f"[dim]Logging in to workspace:[/dim] [bold]{workspace}[/bold]  ({url})"
    )
    console.print(
        "[dim]Create a token at https://skene.ai/settings/tokens[/dim]"
        if "skene.ai" in url
        else "[dim]Obtain an API token from your upstream provider.[/dim]"
    )
    token = getpass.getpass("Paste your API Token: ")

    if not token or not token.strip():
        console.print("[red]No token provided. Login cancelled.[/red]")
        raise typer.Exit(1)

    if not validate_token(api_base, token.strip()):
        console.print("[red]Invalid token or connection failed.[/red]")
        raise typer.Exit(1)

    save_project_upstream(url, workspace)
    cred_path = save_workspace_token(workspace, token.strip())
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
