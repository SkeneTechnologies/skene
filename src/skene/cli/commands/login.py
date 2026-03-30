"""Login and logout commands."""

import typer

from skene.cli.app import app
from skene.cli.auth import cmd_login, cmd_login_status, cmd_logout


@app.command(rich_help_panel="manage")
def login(
    upstream: str | None = typer.Option(
        None,
        "--upstream",
        "-u",
        help="Upstream workspace URL (e.g. https://skene.ai/workspace/my-app)",
    ),
    status: bool = typer.Option(
        False,
        "--status",
        "-s",
        help="Show current login status for this project",
    ),
):
    """
    Log in to upstream for push.

    Saves upstream credentials to .skene.config.

    Use --status to check current login state.

    Examples:

        skene login --upstream https://skene.ai/workspace/my-project
        skene login --status
    """
    if status:
        cmd_login_status()
        return
    cmd_login(upstream_url=upstream)


@app.command(rich_help_panel="manage")
def logout():
    """
    Log out from upstream (remove saved token).

    Does not invalidate the token server-side.
    """
    cmd_logout()
