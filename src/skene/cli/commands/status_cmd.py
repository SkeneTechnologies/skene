"""Show implementation status based on skene/engine.yaml."""

from pathlib import Path

import typer

from skene.cli.app import app, resolve_cli_config
from skene.output import status as output_status
from skene.output import warning


@app.command()
def status(
    path: Path = typer.Argument(
        ".",
        help="Path to the project root",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    context: Path | None = typer.Option(
        None,
        "--context",
        "-c",
        help=(
            "Deprecated: if set to a Skene bundle directory (skene/ or legacy skene-context/), "
            "parent folder is treated as project root"
        ),
    ),
    find_alternatives: bool = typer.Option(
        False,
        "--find-alternatives",
        help="Deprecated for engine status; currently ignored",
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        envvar="SKENE_API_KEY",
        help="Deprecated for engine status; currently ignored",
    ),
    provider: str | None = typer.Option(
        None,
        "--provider",
        "-p",
        help="Deprecated for engine status; currently ignored",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        "-m",
        help="Deprecated for engine status; currently ignored",
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
    Validate engine.yaml and check migration presence for action-enabled features.

    For features with `action`, status verifies the expected trigger/function exists
    under supabase/migrations. Features without `action` are reported as code-only.
    """
    from skene.output_paths import is_bundle_dir_name
    from skene.validators.engine_validator import print_engine_validation_report, validate_engine

    project_root = path.resolve()
    if context is not None and context.exists() and is_bundle_dir_name(context.name):
        project_root = context.resolve().parent

    resolve_cli_config(
        project_root=project_root,
        api_key=api_key,
        provider=provider,
        model=model,
        quiet=quiet,
        debug=debug,
    )

    if find_alternatives:
        warning("--find-alternatives is not supported for engine status checks and will be ignored.")

    output_status(f"Project root: {project_root}")
    result = validate_engine(project_root)
    print_engine_validation_report(result)
    if not result.ok:
        raise typer.Exit(1)
