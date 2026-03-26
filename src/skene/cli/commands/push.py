"""Build Supabase migrations from growth loop telemetry and push to upstream."""

from pathlib import Path
from typing import Any, Optional

import typer

from skene.cli.app import DEFAULT_LOCAL_INGEST_BASE, app, resolve_cli_config
from skene.config import resolve_upstream_token
from skene.growth_loops.schema_sql import DB_TRIGGER_PATH
from skene.output import error, success, warning
from skene.output import status as output_status


@app.command()
def push(
    path: Path = typer.Argument(
        ".",
        help="Project root (output directory for supabase/)",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    context: Optional[Path] = typer.Option(
        None,
        "--context",
        "-c",
        help="Path to skene-context directory (auto-detected if omitted)",
    ),
    loop_id: Optional[str] = typer.Option(
        None,
        "--loop",
        "-l",
        help="Push only this loop (by loop_id); if omitted, pushes all loops with Supabase telemetry",
    ),
    upstream: Optional[str] = typer.Option(
        None,
        "--upstream",
        "-u",
        help="Upstream workspace URL (e.g. https://skene.ai/workspace/my-app)",
    ),
    push_only: bool = typer.Option(
        False,
        "--push-only",
        help="Re-push current output without regenerating",
    ),
    local: bool = typer.Option(
        False,
        "--local",
        help="Build migrations locally without pushing upstream (uses default Skene Cloud ingest URL).",
    ),
    ingest_url: Optional[str] = typer.Option(
        None,
        "--ingest-url",
        help=f"Custom upstream ingest URL (use with --local). Default: {DEFAULT_LOCAL_INGEST_BASE}{DB_TRIGGER_PATH}",
    ),
    proxy_secret: Optional[str] = typer.Option(
        None,
        "--proxy-secret",
        help="Proxy secret for upstream ingest endpoint (use with --local). Default: YOUR_PROXY_SECRET.",
    ),
    init: bool = typer.Option(
        False,
        "--init",
        help="Create or update the base schema migration only, without building telemetry or pushing.",
    ),
    quiet: bool = typer.Option(
        False,
        "-q",
        "--quiet",
        help="Suppress output, show errors only",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Show diagnostic messages and log LLM I/O to ~/.local/state/skene/debug/",
    ),
):
    """
    Build a Supabase migration from growth loop telemetry into /supabase and push to upstream.

    Creates:
    - supabase/migrations/20260201000000_skene_growth_schema.sql: event_log, failed_events, enrichment_map, webhook
    - supabase/migrations/<timestamp>_skene_telemetry.sql: idempotent triggers
      on telemetry-defined tables that INSERT into event_log

    With --init: write base schema migration only (no telemetry, no push).
    With --local: build schema + telemetry migrations only (no push), using default Skene Cloud upstream ingest.
    With --local --ingest-url https://...: same, and bake custom upstream ingest URL into notify_event_log webhook.
    With --upstream: pushes artifacts to remote for backup/versioning.
    Use `skene login` to authenticate.

    Examples:

        skene push
        skene push --init
        skene push --local
        skene push --local --ingest-url https://skene.ai --proxy-secret my-secret
        skene push --upstream https://skene.ai/workspace/my-app
        skene push --loop skene_guard_activation_safety
        skene push --context ./skene-context
    """
    from skene.growth_loops.push import (
        build_loops_to_supabase,
        ensure_base_schema_migration,
        extract_supabase_telemetry,
        push_to_upstream,
    )
    from skene.growth_loops.storage import load_existing_growth_loops

    rc = resolve_cli_config(quiet=quiet, debug=debug)

    if init:
        written = ensure_base_schema_migration(path.resolve())
        success(f"Schema migration: {written}")
        output_status("Run supabase db push to apply.")
        return

    if ingest_url and not local:
        error("--ingest-url can only be used with --local.")
        raise typer.Exit(1)
    if local and upstream:
        error("--local and --upstream cannot be used together.")
        raise typer.Exit(1)
    if local and push_only:
        error("--local and --push-only cannot be used together.")
        raise typer.Exit(1)

    resolved_upstream = None if local else (upstream or rc.config.upstream)
    resolved_token = resolve_upstream_token(rc.config) if resolved_upstream else None

    # Resolve context directory
    if context is None:
        candidates = [
            path / "skene-context",
            Path.cwd() / "skene-context",
        ]
        for candidate in candidates:
            if (candidate / "growth-loops").is_dir():
                context = candidate
                break
        if context is None and not push_only and not local:
            error(
                "Could not find skene-context/growth-loops/ directory.\nUse --context to specify the path explicitly."
            )
            raise typer.Exit(1)
    if (push_only or local) and context is None:
        context = path / "skene-context"
        if not (context / "growth-loops").is_dir():
            context = Path.cwd() / "skene-context"

    loops_with_telemetry: list[dict[str, Any]] = []
    if not push_only:
        ctx_for_loops = context or path / "skene-context"
        if (ctx_for_loops / "growth-loops").is_dir():
            loops = load_existing_growth_loops(ctx_for_loops)
            loops_with_telemetry = [loop for loop in loops if extract_supabase_telemetry(loop)]
            if loop_id:
                loops_with_telemetry = [loop for loop in loops_with_telemetry if loop.get("loop_id") == loop_id]
                if not loops_with_telemetry:
                    error(f"No loop with loop_id '{loop_id}' has Supabase telemetry.")
                    raise typer.Exit(1)
        if not loops_with_telemetry and not local:
            warning(
                "No growth loops with Supabase telemetry found.\n"
                "Add telemetry with type 'supabase' (table, operation, properties) via skene build."
            )
            raise typer.Exit(1)

    if local:
        from skene.growth_loops.schema_sql import _normalize_ingest_url

        default_ingest = DEFAULT_LOCAL_INGEST_BASE + DB_TRIGGER_PATH
        forward_url = _normalize_ingest_url(ingest_url.strip()) if ingest_url and ingest_url.strip() else default_ingest
    else:
        forward_url = None
    secret = proxy_secret or "YOUR_PROXY_SECRET"

    if local and not (ingest_url and ingest_url.strip()):
        output_status("Building migration files with default Skene.ai upstream ingest for reference.")
        output_status(
            "For self-hosted trigger ingests, use: skene push --local --ingest-url https://your-ingest.example.com"
        )
        output_status("To push to upstream managed by Skene.ai, use skene login.")

    try:
        schema_path = ensure_base_schema_migration(path)
        success(f"Schema: {schema_path}")

        if not push_only:
            migration_path = build_loops_to_supabase(
                loops_with_telemetry,
                path,
                forward_url=forward_url,
                proxy_secret=secret,
            )
            success(f"Telemetry: {migration_path}")
        else:
            ctx = context or path / "skene-context"
            if (ctx / "growth-loops").is_dir():
                loops_with_telemetry = [
                    loop for loop in load_existing_growth_loops(ctx) if extract_supabase_telemetry(loop)
                ]

        if resolved_upstream:
            ctx = context or path / "skene-context"
            if push_only:
                migrations_dir = path / "supabase" / "migrations"
                if migrations_dir.exists():
                    telemetry = next(
                        (p for p in sorted(migrations_dir.glob("*.sql")) if "skene_telemetry" in p.name.lower()),
                        None,
                    )
                    if telemetry:
                        success(f"Telemetry: {telemetry}")
                if (ctx / "growth-loops").is_dir():
                    success(f"Growth loops: {ctx / 'growth-loops'}")
            if not resolved_token:
                warning("No token. Run skene login to authenticate.")
            else:
                loops_dir = ctx / "growth-loops" if ctx.exists() else None
                if loops_dir and loops_dir.exists():
                    success(f"Growth loops: {loops_dir}")
                result = push_to_upstream(
                    project_root=path,
                    upstream_url=resolved_upstream,
                    token=resolved_token,
                    loops=loops_with_telemetry,
                    context=context,
                )
                if result.get("ok"):
                    loops_dir = ctx / "growth-loops" if ctx.exists() else None
                    growth_loops_count = len(list(loops_dir.glob("*.json"))) if loops_dir and loops_dir.exists() else 0
                    suffix = "s" if growth_loops_count != 1 else ""
                    sent_parts = [
                        f"growth-loops ({growth_loops_count} file{suffix})",
                        "telemetry.sql",
                    ]
                    success(
                        f"Pushed to upstream commit_hash={result.get('commit_hash', '?')} "
                        f"(package: {', '.join(sent_parts)})"
                    )
                else:
                    msg = result.get("message", "Push failed.")
                    if result.get("error") == "auth":
                        error(msg)
                    else:
                        warning(msg)

        if not push_only and resolved_upstream:
            output_status("Upstream parses the package (growth loops + telemetry.sql) and deploys.")
    except Exception as e:
        error(f"Deploy failed: {e}")
        raise typer.Exit(1)
