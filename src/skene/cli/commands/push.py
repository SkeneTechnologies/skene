"""Push existing engine + trigger artifacts upstream."""

from pathlib import Path

import typer

from skene.cli.app import app, resolve_cli_config
from skene.config import resolve_upstream_token
from skene.engine import collect_engine_trigger_events, default_engine_path, load_engine_document
from skene.growth_loops.push import push_to_upstream
from skene.output import error, success, warning


@app.command()
def push(
    path: Path = typer.Argument(
        ".",
        help="Project root containing the Skene bundle directory",
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
    Push the Skene bundle (engine.yaml, feature-registry.json, trigger SQL) to upstream.

    Counts the files under the bundle directory and uploads the package; the
    upstream workspace decides what to ingest.
    """
    rc = resolve_cli_config(quiet=quiet, debug=debug)
    project_root = path.resolve()

    resolved_upstream = upstream or rc.config.upstream or ""
    user_configured_upstream = bool(resolved_upstream)

    resolved_token = resolve_upstream_token(rc.config)
    if not resolved_token:
        error("No token. Run skene login to authenticate.")
        raise typer.Exit(1)

    engine_path = default_engine_path(project_root)
    trigger_events: list[str] = []
    features_count = 0
    if engine_path.exists():
        try:
            engine_doc = load_engine_document(engine_path, project_root=project_root)
            trigger_events = collect_engine_trigger_events(engine_doc)
            features_count = len(engine_doc.features)
        except Exception:
            pass

    try:
        result = push_to_upstream(
            project_root=project_root,
            upstream_url=resolved_upstream,
            token=resolved_token,
            trigger_events=trigger_events,
            features_count=features_count,
            output_dir=rc.config.output_dir,
        )
    except Exception as exc:
        error(f"Deploy failed: {exc}")
        raise typer.Exit(1) from exc

    if result.get("ok"):
        if result.get("status") == "noop":
            success("Nothing new to deploy.")
        else:
            push_id = result.get("push_id", "?")
            updated_paths = result.get("updated_paths") or []
            artifact_count = result.get("artifact_count", len(updated_paths))
            success(
                f"Pushed {artifact_count} artifact(s); "
                f"{len(updated_paths)} updated upstream (push_id={push_id})"
            )
            for p in updated_paths:
                success(f"  • {p}")
        return

    msg = result.get("message", "Push failed.")
    err_kind = result.get("error")
    if err_kind == "auth":
        error(msg)
    else:
        warning(msg)
        if user_configured_upstream and err_kind in {"not_found", "network", "server"}:
            warning(
                f"Your configured upstream ({resolved_upstream}) seems wrong. "
                "Verify the workspace URL or remove it to use the default Skene Cloud."
            )
    raise typer.Exit(1)
