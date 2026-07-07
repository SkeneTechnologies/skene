"""Attach the CLI to a remote skene server (``skene attach``).

Thin by design (see the phase-5 notes in docs/design/backend-server.md):
verifies the server is reachable and persists ``server_url`` /
``server_token`` in ``.skene.config``, after which ``analyse-journey``
drives that server over HTTP instead of running embedded. ``--clear``
detaches.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import typer

from skene.cli.app import app
from skene.output import console, error, success


def _config_path_for_write() -> Path:
    """The project config if present, else the user config (created if needed)."""
    from skene.config import find_project_config, find_user_config

    project = find_project_config()
    if project is not None:
        return project
    user = find_user_config()
    if user is not None:
        return user
    config_home = os.environ.get("XDG_CONFIG_HOME")
    config_dir = Path(config_home) / "skene" if config_home else Path.home() / ".config" / "skene"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config"


def _upsert_config_keys(path: Path, values: dict[str, str | None]) -> None:
    """Set (or with None, remove) top-level string keys in a TOML config file."""
    lines = path.read_text().splitlines() if path.exists() else ["# skene configuration"]
    for key, value in values.items():
        pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
        lines = [line for line in lines if not pattern.match(line)]
        if value is not None:
            lines.append(f'{key} = "{value}"')
    path.write_text("\n".join(lines) + "\n")
    if os.name != "nt":
        try:
            path.chmod(0o600)
        except OSError:
            pass


@app.command(name="attach", rich_help_panel="manage")
def attach_cmd(
    url: str | None = typer.Argument(None, help="Base URL of a running skene server (e.g. http://127.0.0.1:4906)"),
    token: str | None = typer.Option(
        None,
        "--token",
        envvar="SKENE_SERVER_TOKEN",
        help="Bearer token the server was started with (required for non-local servers).",
    ),
    clear: bool = typer.Option(False, "--clear", help="Detach: remove the stored server URL and token."),
) -> None:
    """
    Attach this machine's skene CLI to a running skene server.

    Verifies the server responds on /health, then stores its URL (and
    token, if given) in .skene.config. Once attached, ``analyse-journey``
    sends runs to that server instead of executing locally. Detach with
    ``skene attach --clear``.
    """
    from skene.cli.remote import RemoteServerError, check_health

    config_path = _config_path_for_write()

    if clear:
        if url is not None:
            error("--clear takes no URL")
            raise typer.Exit(2)
        _upsert_config_keys(config_path, {"server_url": None, "server_token": None})
        success(f"detached (updated {config_path})")
        return

    if url is None:
        error("missing server URL (or use --clear to detach)")
        raise typer.Exit(2)

    url = url.rstrip("/")
    try:
        payload = check_health(url, token)
    except RemoteServerError as e:
        error(str(e))
        raise typer.Exit(1) from e

    _upsert_config_keys(config_path, {"server_url": url, "server_token": token})
    console.print(f"[dim]server version: {payload.get('version', '?')}[/dim]")
    success(f"attached to {url} (stored in {config_path})")
