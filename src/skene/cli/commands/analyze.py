"""Analyze a codebase and generate growth-manifest.json."""

import asyncio
from pathlib import Path

import typer
from pydantic import SecretStr
from rich.panel import Panel

from skene.cli.analysis_helpers import (
    run_analysis,
    run_features_analysis,
    show_analysis_summary,
    show_features_summary,
)
from skene.cli.app import app, resolve_cli_config
from skene.cli.output_writers import write_growth_template, write_product_docs
from skene.cli.sample_report import show_sample_report
from skene.output import console, success, warning


@app.command()
def analyze(
    path: Path = typer.Argument(
        ".",
        help="Path to codebase to analyze",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    output: Path | None = typer.Option(
        None,
        "-o",
        "--output",
        help="Output path for growth-manifest.json",
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
        help="LLM provider to use (openai, gemini, anthropic/claude, lmstudio, ollama, generic, skene)",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        "-m",
        help="LLM model name (e.g., gemini-3-flash-preview for v1beta API)",
    ),
    base_url: str | None = typer.Option(
        None,
        "--base-url",
        envvar="SKENE_BASE_URL",
        help="Base URL for API endpoint (required for generic; optional for skene local dev)",
    ),
    quiet: bool = typer.Option(
        False,
        "-q",
        "--quiet",
        help="Suppress status messages; show only errors and final results",
    ),
    product_docs: bool = typer.Option(
        False,
        "--product-docs",
        help="Generate product-docs.md with user-facing feature documentation",
    ),
    features: bool = typer.Option(
        False,
        "--features",
        help="Only analyze growth features and update feature-registry.json",
    ),
    exclude: list[str] | None = typer.Option(
        None,
        "--exclude",
        "-e",
        help=(
            "Folder names to exclude from analysis (can be used multiple times). "
            "Can also be set in .skene.config as exclude_folders. "
            "Example: --exclude tests --exclude vendor"
        ),
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Show diagnostic messages and log all LLM input/output to ~/.local/state/skene/debug/",
    ),
    no_fallback: bool = typer.Option(
        False,
        "--no-fallback",
        help="Disable model fallback on rate limits; retry same model instead",
    ),
):
    """
    Analyze a codebase and generate growth-manifest.json.

    Scans your codebase to detect:
    - Technology stack (framework, language, database, etc.)
    - Current growth features (features with growth potential)
    - Growth opportunities (missing features that could drive growth)

    With --product-docs flag:
    - Collects product overview (tagline, value proposition, target audience)
    - Collects user-facing feature documentation from codebase
    - Generates product-docs.md: User-friendly documentation of features and roadmap

    With --features flag:
    - Only runs growth features analysis
    - Updates skene-context/feature-registry.json (with growth-loops mapping)

    Examples:

        # Analyze current directory (uvx)
        uvx skene analyze .
        # Or: uvx skene analyze .

        # Analyze specific path with custom output
        uvx skene analyze ./my-project -o manifest.json

        # With API key
        uvx skene analyze . --api-key "your-key"

        # Generate product documentation
        uvx skene analyze . --product-docs

        # Features only (registry update)
        uvx skene analyze . --features
    """
    rc = resolve_cli_config(
        api_key=api_key,
        provider=provider,
        model=model,
        base_url=base_url,
        quiet=quiet,
        debug=debug,
    )

    # Handle output path: if it's a directory, append default filename
    if output:
        # Resolve to absolute path
        if output.is_absolute():
            resolved_output = output.resolve()
        else:
            resolved_output = (Path.cwd() / output).resolve()

        # If path exists and is a directory, or has no file extension, append default filename
        if resolved_output.exists() and resolved_output.is_dir():
            resolved_output = (resolved_output / "growth-manifest.json").resolve()
        elif not resolved_output.suffix:
            resolved_output = (resolved_output / "growth-manifest.json").resolve()
        else:
            resolved_output = resolved_output.resolve()
    else:
        resolved_output = Path(rc.config.output_dir) / "growth-manifest.json"

    # If no API key and not using local provider, show sample report or require key
    if not rc.api_key and not rc.is_local:
        if features:
            warning(
                "No API key provided. Feature analysis requires an LLM.\n"
                "Set --api-key, SKENE_API_KEY env var, or add to .skene.config"
            )
            raise typer.Exit(1)
        warning(
            "No API key provided. Showing sample growth analysis preview.\n"
            "For full AI-powered analysis, set --api-key, SKENE_API_KEY env var, or add to .skene.config\n"
        )
        show_sample_report(path, output, exclude_folders=exclude if exclude else None)
        return

    resolved_api_key = rc.api_key
    if not resolved_api_key and rc.is_local:
        resolved_api_key = rc.provider  # Dummy key for local server

    # If features only, use features mode
    mode_str = "docs" if product_docs else ("features" if features else "growth")
    console.print(
        Panel.fit(
            f"[bold blue]Analyzing codebase[/bold blue]\n"
            f"Path: {path}\n"
            f"Provider: {rc.provider}\n"
            f"Model: {rc.model}\n"
            f"Mode: {mode_str}",
            title="skene",
        )
    )

    # Collect exclude folders from config and CLI
    exclude_folders = list(rc.config.exclude_folders) if rc.config.exclude_folders else []
    if exclude:
        exclude_folders = list(set(exclude_folders + exclude))

    # Run async analysis
    from skene.llm import create_llm_client

    async def execute_analysis():
        llm = create_llm_client(
            rc.provider,
            SecretStr(resolved_api_key),
            rc.model,
            base_url=rc.base_url,
            debug=rc.debug,
            no_fallback=no_fallback,
        )

        if features:
            result, manifest_data = await run_features_analysis(
                path,
                resolved_output,
                llm,
                rc.debug,
                exclude_folders=exclude_folders if exclude_folders else None,
            )
            registry_path = resolved_output.parent / "feature-registry.json"
            if result is None:
                raise typer.Exit(1)
            success(f"Feature registry updated: {registry_path}")
            if manifest_data:
                show_features_summary(manifest_data)
        else:
            result, manifest_data = await run_analysis(
                path,
                resolved_output,
                llm,
                rc.debug,
                product_docs,
                exclude_folders=exclude_folders if exclude_folders else None,
            )

            if result is None:
                raise typer.Exit(1)

            # Generate product docs if requested
            if product_docs:
                write_product_docs(manifest_data, resolved_output)

            template_data = await write_growth_template(
                llm,
                manifest_data,
                resolved_output,
            )

            success(f"Manifest saved to: {resolved_output}")

            if result.data:
                show_analysis_summary(result.data, template_data)

    asyncio.run(execute_analysis())
