"""Generate a journey.yaml from a repo's codebase and its SQL schema.

Replaces the legacy schema/growth/plan pipeline. The main skene agent
spawns two subagents in parallel — one over a directory of pre-exported
SQL files (or a live database), one over the repo filesystem — which emit
candidate milestones; its ``finalize_journey`` tool merges them,
classifies each into one of seven canonical lifecycle stages, and
assembles a validated Journey written to ``journey.yaml``.

See :mod:`skene.core.journey` for the flow.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.panel import Panel
from rich.table import Table

from skene.cli._journey_runner import (
    build_llm,
    require_llm_credentials,
    resolve_artifact_path,
    resolve_base_path,
    resolve_cli_config,
)
from skene.cli.app import app
from skene.core.embedded import run_journey_embedded
from skene.core.redact import redact_db_url as _redact_db_url
from skene.output import console, error
from skene.output_paths import DEFAULT_OUTPUT_DIR
from skene.schema import JourneyAnalyseRequest


@app.command(name="analyse-journey")
def analyse_journey_cmd(
    path: Path | None = typer.Argument(
        None,
        help="Path to codebase to analyse (omit for current directory)",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    schema_dir: Path | None = typer.Option(
        None,
        "--schema-dir",
        help=("Directory of pre-exported *.sql files for the schema agent."),
    ),
    db_url: str | None = typer.Option(
        None,
        "--db-url",
        envvar="SKENE_DB_URL",
        help=(
            "PostgreSQL connection string to introspect for the schema agent, "
            "as an alternative to --schema-dir. Must be a complete connection "
            "string. Never stored. Example: postgresql://user:pass@host:5432/db"
        ),
    ),
    output: Path = typer.Option(
        Path(f"{DEFAULT_OUTPUT_DIR}/journey.yaml"),
        "-o",
        "--output",
        help="Output path for journey.yaml",
    ),
    product_name: str | None = typer.Option(
        None,
        "--product-name",
        help="Product name in the output (default: inferred from the repo directory name)",
    ),
    schema_max_turns: int = typer.Option(
        150,
        "--schema-max-turns",
        min=1,
        max=500,
        help="Maximum agent turns for the schema agent",
    ),
    code_max_turns: int = typer.Option(
        200,
        "--code-max-turns",
        min=1,
        max=500,
        help="Maximum agent turns for the code agent",
    ),
    classify_concurrency: int = typer.Option(
        8,
        "--classify-concurrency",
        min=1,
        max=64,
        help="Parallel classifier requests",
    ),
    no_specialize: bool = typer.Option(
        False,
        "--no-specialize",
        help="Skip stage specialization; use canonical stage vocabulary",
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        envvar="SKENE_API_KEY",
        help="API key for LLM provider (or set SKENE_API_KEY env var)",
    ),
    provider: str | None = typer.Option(
        None,
        "--provider",
        "-p",
        help="LLM provider (openai, gemini, anthropic/claude, lmstudio, ollama, generic, skene)",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        "-m",
        help="LLM model name",
    ),
    base_url: str | None = typer.Option(
        None,
        "--base-url",
        envvar="SKENE_BASE_URL",
        help="Base URL for API endpoint",
    ),
    quiet: bool = typer.Option(
        False,
        "-q",
        "--quiet",
        help="Suppress status messages; show only errors and final results",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Show diagnostic messages and log all LLM input/output",
    ),
    no_fallback: bool = typer.Option(
        False,
        "--no-fallback",
        help="Disable model fallback on rate limits; retry same model instead",
    ),
    server: str | None = typer.Option(
        None,
        "--server",
        envvar="SKENE_SERVER_URL",
        help=(
            "Run the analysis on a remote skene server instead of locally "
            "(default: the server stored by `skene attach`, if any). Paths "
            "are interpreted on the server's filesystem."
        ),
    ),
    server_token: str | None = typer.Option(
        None,
        "--server-token",
        envvar="SKENE_SERVER_TOKEN",
        help="Bearer token for --server (default: the token stored by `skene attach`).",
    ),
    auto_publish: bool = typer.Option(
        False,
        "--auto-publish",
        hidden=True,
        help=(
            "After writing journey.yaml, publish it to Skene Cloud when linked to a "
            "skene workspace and no journey.yaml exists upstream yet. Set by the TUI; "
            "a no-op for any other provider or when a remote journey already exists."
        ),
    ),
) -> None:
    """
    Generate a journey.yaml describing the user lifecycle of the target product.

    Provide a codebase path, a ``--schema-dir`` of *.sql files, or both. The
    main agent runs two subagents in parallel:

    \b
      - Schema agent: walks the parsed SQL schema and emits a milestone for
        every user-facing table.
      - Code agent: walks the repo and emits a milestone for every
        user-facing route, handler, analytics call, or job.

    The candidates are merged, classified into discovery / onboarding /
    activation / engagement / retention / expansion / virality, and
    assembled into a single validated Journey document.

    Examples:

    \b
        skene analyse-journey ./my-app --schema-dir ./supabase-schemas
        skene analyse-journey --schema-dir ./schemas -o journey.json
        skene analyse-journey ./my-app  # code-only mode (no SQL)
        skene analyse-journey --db-url postgresql://user:pass@host:5432/db
    """
    # --schema-dir and --db-url are mutually exclusive.
    if schema_dir is not None and db_url is not None:
        error("--schema-dir and --db-url are mutually exclusive")
        raise typer.Exit(2)

    # At least one input is required.
    if path is None and schema_dir is None and db_url is None:
        error("at least one of PATH, --schema-dir, or --db-url is required")
        raise typer.Exit(2)

    base_path = resolve_base_path(path) if path is not None else None
    schema_path = schema_dir.resolve() if schema_dir is not None else None
    if schema_path is not None:
        if not schema_path.exists():
            error(f"--schema-dir does not exist: {schema_path}")
            raise typer.Exit(1)
        if not schema_path.is_dir():
            error(f"--schema-dir is not a directory: {schema_path}")
            raise typer.Exit(1)

    # Config resolution needs a project root; fall back to cwd if only --schema-dir is given.
    config_root = base_path if base_path is not None else Path.cwd()
    rc = resolve_cli_config(
        project_root=config_root,
        api_key=api_key,
        provider=provider,
        model=model,
        base_url=base_url,
        quiet=quiet,
        debug=debug,
    )

    # Attached to a server (via `skene attach` or --server)? Run remotely —
    # the server holds the LLM credentials, so none are needed locally.
    server_url = server or rc.config.get("server_url")
    if server_url:
        _run_remote(
            server_url,
            server_token or rc.config.get("server_token"),
            config_root=config_root,
            base_path=base_path,
            schema_path=schema_path,
            db_url=db_url,
            output=output,
            product_name=product_name,
            schema_max_turns=schema_max_turns,
            code_max_turns=code_max_turns,
            classify_concurrency=classify_concurrency,
            specialize=not no_specialize,
        )
        return

    resolved_api_key = require_llm_credentials(rc, "analyse-journey")

    journey_path = resolve_artifact_path(output, "journey.yaml")
    journey_path.parent.mkdir(parents=True, exist_ok=True)

    db_display = _redact_db_url(db_url) if db_url is not None else None
    resolved_product_name = product_name or _infer_product_name(base_path, schema_path, db_url)

    # The run itself goes through the embedded server core (same code path
    # as ``POST /journey/analyse``), so this CLI invocation leaves a session
    # trace in the skene DB like any served run. Live-DB introspection also
    # happens inside the run; the URL is never persisted.
    request = JourneyAnalyseRequest(
        path=str(base_path) if base_path is not None else None,
        schema_dir=str(schema_path) if schema_path is not None else None,
        db_url=db_url,
        product_name=resolved_product_name,
        output=str(journey_path),
        classify_concurrency=classify_concurrency,
        schema_max_turns=schema_max_turns,
        code_max_turns=code_max_turns,
        specialize=not no_specialize,
    )
    specialize = not no_specialize

    _render_kickoff(
        title="skene · analyse-journey",
        base_path=base_path,
        schema_dir=schema_path,
        db_display=db_display,
        rc=rc,
        product_name=resolved_product_name,
        journey_path=journey_path,
        specialize=specialize,
    )

    llm = build_llm(rc, resolved_api_key, no_fallback=no_fallback)

    import asyncio

    try:
        journey = asyncio.run(run_journey_embedded(request, llm, directory=config_root))
    except Exception as e:  # noqa: BLE001 — surface any failure to the user
        error(f"analysis failed: {e}")
        raise typer.Exit(1) from e

    _render_summary(journey_path, journey)

    _maybe_auto_publish(rc, config_root, journey_path=journey_path, enabled=auto_publish)


def _run_remote(
    server_url: str,
    server_token: str | None,
    *,
    config_root: Path,
    base_path: Path | None,
    schema_path: Path | None,
    db_url: str | None,
    output: Path,
    product_name: str | None,
    schema_max_turns: int,
    code_max_turns: int,
    classify_concurrency: int,
    specialize: bool,
) -> None:
    """Drive the analysis on an attached server; paths are server-side."""
    import asyncio

    from skene.cli.remote import RemoteServerError, check_health, run_journey_remote

    try:
        check_health(server_url, server_token)
    except RemoteServerError as e:
        error(f"{e}\n(re-run `skene attach <url>` or `skene attach --clear` to run locally)")
        raise typer.Exit(1) from e

    request = JourneyAnalyseRequest(
        path=str(base_path) if base_path is not None else None,
        schema_dir=str(schema_path) if schema_path is not None else None,
        db_url=db_url,
        product_name=product_name,
        output=str(output) if output != Path(f"{DEFAULT_OUTPUT_DIR}/journey.yaml") else None,
        classify_concurrency=classify_concurrency,
        schema_max_turns=schema_max_turns,
        code_max_turns=code_max_turns,
        specialize=specialize,
    )
    console.print(f"[bold]skene · analyse-journey[/bold] [dim]→ remote server {server_url}[/dim]")
    try:
        artifact = asyncio.run(run_journey_remote(server_url, server_token, str(config_root), request))
    except KeyboardInterrupt:
        error("aborted")
        raise typer.Exit(130) from None
    except RemoteServerError as e:
        error(f"analysis failed: {e}")
        raise typer.Exit(1) from e

    summary = artifact.get("summary") or ""
    if summary:
        console.print(summary)
    console.print(f"\n[green]✓[/green] wrote {artifact.get('path')} (on {server_url})")


def _maybe_auto_publish(rc, project_root: Path, *, journey_path: Path, enabled: bool) -> None:
    """Publish the freshly written journey.yaml to Skene Cloud on first run.

    Gated on (in order): the TUI-only ``--auto-publish`` opt-in, the skene
    provider with a linked workspace (upstream URL + token), and the absence of
    a journey.yaml upstream. A failed or indeterminate presence check skips
    publishing silently — we never push unless skene.ai definitively reports no
    journey. Never raises: a publish failure must not fail journey analysis.

    The push is anchored to ``journey_path``'s directory (where we just wrote the
    journey), not ``config.output_dir`` — the latter can resolve to a stale legacy
    ``skene/`` bundle and silently exclude the freshly written ``journey.yaml``.
    """
    from skene.output import debug, success, warning

    if not enabled:
        debug("auto-publish: skipped (flag not set; not a linked TUI run)")
        return

    from skene.config import resolve_upstream_token
    from skene.growth_loops.push import publish_bundle
    from skene.growth_loops.upstream import (
        _api_base_from_upstream,
        journey_exists_upstream,
    )

    config = rc.config
    if config.provider != "skene":
        debug(f"auto-publish: skipped (provider is {config.provider!r}, not 'skene')")
        return

    upstream = config.upstream
    token = resolve_upstream_token(config)
    if not upstream or not token:
        debug(
            "auto-publish: skipped (not linked: "
            f"upstream={'set' if upstream else 'missing'}, "
            f"token={'set' if token else 'missing'})"
        )
        return

    api_base = _api_base_from_upstream(upstream)

    # The workspace is resolved server-side from the token (1:1), so a "present"
    # result means *this token's* workspace already has a journey.yaml.
    present = journey_exists_upstream(api_base, token)
    if present is not False:
        # True (already published) or None (indeterminate) → leave it alone.
        reason = "already present upstream" if present else "presence check indeterminate"
        debug(f"auto-publish: skipped ({reason})")
        return

    debug("auto-publish: publishing journey (workspace empty upstream)")

    try:
        result = publish_bundle(
            project_root,
            config,
            upstream=upstream,
            token=token,
            output_dir=str(journey_path.parent),
        )
    except Exception as exc:  # noqa: BLE001 — auto-publish is best-effort
        warning(f"Could not publish journey to Skene Cloud: {exc}")
        return

    if result.get("ok"):
        success("✓ Published journey to Skene Cloud.")
    else:
        warning(f"Could not publish journey to Skene Cloud: {result.get('message', 'unknown error')}")


def _infer_product_name(
    repo_root: Path | None,
    schema_dir: Path | None,
    db_url: str | None = None,
) -> str:
    if repo_root is not None:
        return repo_root.name or "Product"
    if db_url is not None:
        # Extract database name from DSN: postgresql://user:pass@host:port/dbname
        try:
            # Remove scheme
            rest = db_url.split("://", 1)[-1]
            # Skip credentials (user:pass@)
            if "@" in rest:
                rest = rest.split("@")[-1]
            # After host:port/, the next segment is the database name
            path_part = rest.split("/", 1)
            if len(path_part) > 1 and path_part[1]:
                return path_part[1].split("?")[0].split("&")[0] or "Product"
        except Exception:  # noqa: BLE001
            pass
        return "Product"
    if schema_dir is not None:
        return schema_dir.name or "Product"
    return "Product"


def _render_kickoff(
    *,
    title: str,
    base_path: Path | None,
    schema_dir: Path | None,
    db_display: str | None,
    rc,
    product_name: str,
    journey_path: Path,
    specialize: bool,
) -> None:
    # Build schema display: DB URL takes precedence, then schema_dir.
    if db_display is not None:
        schema_display = f"[dim]{db_display}[/dim]"
    elif schema_dir is not None:
        schema_display = str(schema_dir)
    else:
        schema_display = "[dim](none)[/dim]"

    lines = [
        f"[bold]Product[/bold]    {product_name}",
        f"[bold]Repo[/bold]       {base_path or '[dim](none)[/dim]'}",
        f"[bold]Schema[/bold]     {schema_display}",
        f"[bold]Output[/bold]     {journey_path}",
        f"[bold]Provider[/bold]   {rc.provider} · [dim]{rc.model}[/dim]",
        f"[bold]Specialize[/bold] {'yes' if specialize else 'no'}",
    ]
    console.print(Panel.fit("\n".join(lines), title=title, border_style="blue"))


def _render_summary(journey_path: Path, journey) -> None:
    table = Table(title="Journey summary", title_style="bold", show_lines=False)
    table.add_column("Stage", style="bold")
    table.add_column("Milestones", justify="right")
    for stage in journey.stages:
        table.add_row(f"{stage.id} ({stage.name})", str(len(stage.milestones)))
    table.add_row("[dim]total[/dim]", str(sum(len(s.milestones) for s in journey.stages)))
    console.print()
    console.print(table)
    console.print(f"\n[green]✓[/green] wrote {journey_path}")
