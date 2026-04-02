"""Push existing engine + trigger artifacts upstream."""

from pathlib import Path

import typer

from skene.cli.app import app, resolve_cli_config
from skene.config import resolve_upstream_token
from skene.engine import collect_engine_trigger_events, default_engine_path, load_engine_document
from skene.feature_registry import registry_path_for_project
from skene.growth_loops.push import find_trigger_migration, push_to_upstream
from skene.output import error, success, warning
from skene.output import status as output_status


@app.command()
def push(
    path: Path = typer.Argument(
        ".",
        help="Project root (must contain skene/engine.yaml and supabase/migrations)",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    upstream: str | None = typer.Option(
        None,
        "--upstream",
        "-u",
        help="Upstream workspace URL (e.g. https://skene.ai/workspace/my-app)",
    ),
    push_only: bool = typer.Option(
        False,
        "--push-only",
        help="Legacy no-op flag; push already uses existing artifacts only",
    ),
    context: Path | None = typer.Option(
        None,
        "--context",
        "-c",
        help="Deprecated: no longer used",
    ),
    loop_id: str | None = typer.Option(
        None,
        "--loop",
        "-l",
        help="Deprecated: loop filtering is removed; engine.yaml is the source of truth",
    ),
    local: bool = typer.Option(
        False,
        "--local",
        help="Deprecated: migration generation moved to `skene build`",
    ),
    ingest_url: str | None = typer.Option(
        None,
        "--ingest-url",
        help="Deprecated: migration generation moved to `skene build`",
    ),
    proxy_secret: str | None = typer.Option(
        None,
        "--proxy-secret",
        help="Deprecated: migration generation moved to `skene build`",
    ),
    init: bool = typer.Option(
        False,
        "--init",
        help="Deprecated: migration generation moved to `skene build`",
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
    Push existing `skene/engine.yaml`, `feature-registry.json`, and trigger migration SQL to upstream.

    This command no longer builds migrations. Run `skene build` first.
    """
    rc = resolve_cli_config(quiet=quiet, debug=debug)
    project_root = path.resolve()

    deprecated_used = init or local or bool(ingest_url) or bool(proxy_secret) or bool(context) or bool(loop_id)
    if deprecated_used:
        error(
            "push no longer builds migrations. Run `skene build` first, then `skene push`.\n"
            "Deprecated flags: --init, --local, --ingest-url, --proxy-secret, --context, --loop"
        )
        raise typer.Exit(1)

    resolved_upstream = upstream or rc.config.upstream
    if not resolved_upstream:
        error("No upstream configured. Use --upstream or set upstream in .skene.config.")
        raise typer.Exit(1)

    resolved_token = resolve_upstream_token(rc.config)
    if not resolved_token:
        warning("No token. Run skene login to authenticate.")
        raise typer.Exit(1)

    engine_path = default_engine_path(project_root)
    if not engine_path.exists():
        error(f"Engine file not found: {engine_path}\nRun `skene build` first.")
        raise typer.Exit(1)

    migrations_dir = project_root / "supabase" / "migrations"
    trigger_path = find_trigger_migration(migrations_dir)
    if trigger_path is None:
        error(
            "No trigger migration found in supabase/migrations.\n"
            "Run `skene build` first so migration artifacts are generated."
        )
        raise typer.Exit(1)

    schema_path = (
        next((p for p in sorted(migrations_dir.glob("*.sql")) if "skene_growth_schema" in p.name.lower()), None)
        if migrations_dir.exists()
        else None
    )
    if schema_path is None:
        warning("Base schema migration not found (skene_growth_schema). Did you run skene build recently?")

    registry_path = registry_path_for_project(project_root, rc.config.output_dir)
    if registry_path.is_file():
        success(f"Feature registry: {registry_path}")
    else:
        warning(
            f"No feature registry at {registry_path}. Run `skene build` (or analyze) so the registry exists; "
            "push will omit it from the package until then."
        )

    if push_only:
        output_status("`--push-only` is now implicit; pushing existing artifacts.")

    success(f"Engine: {engine_path}")
    success(f"Trigger: {trigger_path}")
    if schema_path:
        success(f"Schema: {schema_path}")

    try:
        engine_doc = load_engine_document(engine_path)
        trigger_events = collect_engine_trigger_events(engine_doc)

        result = push_to_upstream(
            project_root=project_root,
            upstream_url=resolved_upstream,
            token=resolved_token,
            trigger_events=trigger_events,
            features_count=len(engine_doc.features),
            output_dir=rc.config.output_dir,
        )
        if result.get("ok"):
            success(
                f"Pushed to upstream commit_hash={result.get('commit_hash', '?')} "
                "(package: engine_yaml, feature_registry_json, trigger_sql)"
            )
            output_status("Upstream parses the package and deploys.")
            return

        msg = result.get("message", "Push failed.")
        if result.get("error") == "auth":
            error(msg)
        else:
            warning(msg)
        raise typer.Exit(1)
    except Exception as exc:
        error(f"Deploy failed: {exc}")
        raise typer.Exit(1)
