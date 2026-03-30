"""Show implementation status of growth loop requirements."""

import asyncio
from pathlib import Path
from typing import Any

import typer
from pydantic import SecretStr

from skene.cli.app import app, resolve_cli_config
from skene.output import console, error, warning
from skene.output import status as output_status


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
        help="Path to skene-context directory (auto-detected if omitted)",
    ),
    find_alternatives: bool = typer.Option(
        False,
        "--find-alternatives",
        help="Use LLM to find existing functions that might fulfill missing requirements (requires API key)",
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        envvar="SKENE_API_KEY",
        help="API key for LLM provider (required for --find-alternatives)",
    ),
    provider: str | None = typer.Option(
        None,
        "--provider",
        "-p",
        help="LLM provider: openai, gemini, anthropic, ollama, generic, skene (uses config if not provided)",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        "-m",
        help="LLM model (uses provider default if not provided)",
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
    Show implementation status of growth loop requirements.

    Loads all growth loop JSON definitions from skene-context/growth-loops/
    and uses AST parsing to verify that required files, functions, and
    patterns are implemented. Displays a report showing which requirements
    are met and which are missing.

    With --find-alternatives, uses LLM to search for existing functions that
    might fulfill missing requirements, helping discover duplicate implementations.

    Examples:

        skene status
        skene status ./my-project --context ./my-project/skene-context
        skene status --find-alternatives --api-key "your-key"
    """
    from skene.validators.loop_validator import (
        ValidationEvent,
        clear_event_listeners,
        print_validation_report,
        register_event_listener,
        validate_all_loops,
    )

    rc = resolve_cli_config(
        api_key=api_key,
        provider=provider,
        model=model,
        quiet=quiet,
        debug=debug,
    )

    # Resolve the context directory
    if context is None:
        # Auto-detect: look for skene-context relative to path
        candidates = [
            path / "skene-context",
            Path.cwd() / "skene-context",
        ]
        for candidate in candidates:
            if (candidate / "growth-loops").is_dir():
                context = candidate
                break
        if context is None:
            error(
                "Could not find skene-context/growth-loops/ directory.\nUse --context to specify the path explicitly."
            )
            raise typer.Exit(1)

    loops_dir = context / "growth-loops"
    if not loops_dir.is_dir():
        error(f"Growth loops directory not found: {loops_dir}")
        raise typer.Exit(1)

    # Setup LLM client if find_alternatives is enabled
    llm_client = None
    if find_alternatives:
        if not rc.api_key:
            warning(
                "--find-alternatives requires an API key.\nProvide --api-key or set SKENE_API_KEY environment variable."
            )
            raise typer.Exit(1)

        from skene.llm.factory import create_llm_client

        try:
            llm_client = create_llm_client(
                provider=rc.provider,
                api_key=SecretStr(rc.api_key),
                model_name=rc.model,
                base_url=rc.base_url,
                debug=rc.debug,
            )
            output_status("Semantic matching enabled (finding alternative implementations)")
        except Exception as exc:
            error(f"Failed to initialize LLM client: {exc}")
            raise typer.Exit(1)

    output_status(f"Project root: {path}")
    output_status(f"Context dir:  {context}")
    output_status(f"Loops dir:    {loops_dir}")
    console.print()

    # Register event listener for simple text output
    def event_listener(event: ValidationEvent, payload: dict[str, Any]) -> None:
        """Display validation events as simple text messages."""
        if event == ValidationEvent.LOOP_VALIDATION_STARTED:
            loop_name = payload.get("loop_name", "Unknown Loop")
            output_status(f"Validating {loop_name}...")
        elif event == ValidationEvent.REQUIREMENT_MET:
            req_type = payload.get("type", "")
            if req_type == "file":
                file_path = payload.get("path", "")
                output_status(f"  File requirement met: {file_path}...")
            elif req_type == "function":
                func_name = payload.get("name", "")
                output_status(f"  Function requirement met: {func_name}...")
        elif event == ValidationEvent.LOOP_COMPLETED:
            loop_name = payload.get("loop_name", "Unknown Loop")
            output_status(f"Loop complete: {loop_name}...")
        # Skip VALIDATION_TIME event - not user-facing

    register_event_listener(event_listener)

    async def _run_status() -> list:
        return await validate_all_loops(
            context_dir=context,
            project_root=path,
            llm_client=llm_client,
            find_alternatives=find_alternatives,
        )

    try:
        results = asyncio.run(_run_status())
    finally:
        clear_event_listeners()

    console.print()
    print_validation_report(results)
