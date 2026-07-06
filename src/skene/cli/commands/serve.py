"""Run the skene backend server headless (``skene serve``)."""

from __future__ import annotations

from pathlib import Path

import typer

from skene.cli.app import app, resolve_cli_config
from skene.output import console, error

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}

DEFAULT_PORT = 4906


@app.command(name="serve", rich_help_panel="manage")
def serve_cmd(
    port: int = typer.Option(DEFAULT_PORT, "--port", help="Port to listen on"),
    host: str = typer.Option("127.0.0.1", "--host", help="Interface to bind (non-local requires --token)"),
    token: str | None = typer.Option(
        None,
        "--token",
        envvar="SKENE_SERVER_TOKEN",
        help="Bearer token clients must present. Required when binding a non-local interface.",
    ),
    db_path: Path | None = typer.Option(
        None,
        "--db-path",
        envvar="SKENE_DB_PATH",
        help="SQLite database location (default: ~/.local/share/skene/skene.db)",
    ),
    api_key: str | None = typer.Option(None, "--api-key", envvar="SKENE_API_KEY", help="API key for LLM provider"),
    provider: str | None = typer.Option(None, "--provider", "-p", help="LLM provider for prompt runs"),
    model: str | None = typer.Option(None, "--model", "-m", help="LLM model name"),
    base_url: str | None = typer.Option(None, "--base-url", envvar="SKENE_BASE_URL", help="Base URL for API endpoint"),
    quiet: bool = typer.Option(False, "-q", "--quiet", help="Suppress status messages"),
    debug: bool = typer.Option(False, "--debug", help="Show diagnostic messages and log all LLM input/output"),
) -> None:
    """
    Run the skene backend server.

    Serves the HTTP API + SSE event stream that the CLI and TUI clients
    drive (see ``/doc`` for the OpenAPI spec). Binds 127.0.0.1 by default;
    binding any other interface requires a bearer token.
    """
    import uvicorn

    from skene.server import create_app

    if host not in _LOCAL_HOSTS and token is None:
        error(f"binding non-local interface {host!r} requires --token (or SKENE_SERVER_TOKEN)")
        raise typer.Exit(2)

    # Resolve LLM config once at startup; prompt runs build a client lazily so
    # the server still starts (and serves journey-free routes) without a key.
    rc = resolve_cli_config(
        api_key=api_key, provider=provider, model=model, base_url=base_url, quiet=quiet, debug=debug
    )

    def llm_factory():
        from skene.cli._journey_runner import build_llm

        if not rc.api_key and not rc.is_local:
            raise RuntimeError("no LLM credentials configured — restart the server with --api-key or set SKENE_API_KEY")
        return build_llm(rc, rc.api_key or rc.provider, no_fallback=False)

    server_app = create_app(db_path=db_path, llm_factory=llm_factory, auth_token=token)
    console.print(f"[bold]skene[/bold] server listening on http://{host}:{port} (provider: {rc.provider})")
    uvicorn.run(server_app, host=host, port=port, log_level="debug" if debug else "info")
