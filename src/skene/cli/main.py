"""
CLI for skene PLG analysis toolkit.

Primary usage (uvx - zero installation):
    uvx skene analyze .
    uvx skene plan

Alternative usage (pip install):
    skene analyze .
    skene plan

Configuration files (optional):
    Project-level: ./.skene.config
    User-level: ~/.config/skene/config
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import click
import typer
from pydantic import SecretStr
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from typer.core import TyperGroup

from skene import __version__
from skene.cli.analysis_helpers import (
    run_analysis,
    run_features_analysis,
    run_generate_plan,
    show_analysis_summary,
    show_features_summary,
)
from skene.cli.auth import cmd_login, cmd_login_status, cmd_logout
from skene.cli.config_manager import (
    create_sample_config,
    interactive_config_setup,
    save_config,
    show_config_status,
)
from skene.cli.features import features_app
from skene.cli.output_writers import write_growth_template, write_product_docs
from skene.cli.prompt_builder import (
    build_prompt_from_template,
    build_prompt_with_llm,
    extract_technical_execution,
    open_cursor_deeplink,
    run_claude,
    save_prompt_to_file,
)
from skene.cli.sample_report import show_sample_report
from skene.config import default_model_for_provider, load_config, resolve_upstream_token
from skene.growth_loops.schema_sql import DB_TRIGGER_PATH
from skene.planner import find_plan_steps_path

# Command order and groups for --help
_COMMAND_ORDER = [
    "analyze",
    "plan",
    "build",
    "status",
    "push",
    "config",
    "validate",
    "login",
    "logout",
    "features",
    "chat",
]


class SectionedHelpGroup(TyperGroup):
    """TyperGroup that lists commands in a specific order for help output."""

    def list_commands(self, ctx: click.Context) -> list[str]:
        ordered = [c for c in _COMMAND_ORDER if c in self.commands]
        extra = [c for c in self.commands if c not in _COMMAND_ORDER]
        return ordered + extra


app = typer.Typer(
    name="skene",
    help="PLG analysis toolkit for codebases. Analyze code, detect growth opportunities.",
    add_completion=False,
    no_args_is_help=True,
    cls=SectionedHelpGroup,
)

console = Console()

# Default upstream ingest URL when --local is used without --ingest-url
DEFAULT_LOCAL_INGEST_BASE = "https://www.skene.ai"


def _run_cli(app_fn) -> None:
    """Run CLI app."""
    app_fn()


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        console.print(f"[bold]skene[/bold] version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
):
    """
    skene - PLG analysis toolkit for codebases.

    Analyze your codebase, detect growth opportunities, and generate documentation.

    Workflow suggestion:
        analyze -> plan

    Quick start with uvx (no installation required):

        uvx skene analyze .
        # Or: uvx skene analyze .

    Or install with pip:

        pip install skene
        skene analyze .
        # Or: skene analyze .
    """
    pass


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
    output: Optional[Path] = typer.Option(
        None,
        "-o",
        "--output",
        help="Output path for growth-manifest.json",
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        envvar="SKENE_API_KEY",
        help="API key for LLM provider (or set SKENE_API_KEY env var)",
    ),
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        "-p",
        help="LLM provider to use (openai, gemini, anthropic/claude, lmstudio, ollama, generic)",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="LLM model name (e.g., gemini-3-flash-preview for v1beta API)",
    ),
    base_url: Optional[str] = typer.Option(
        None,
        "--base-url",
        envvar="SKENE_BASE_URL",
        help="Base URL for OpenAI-compatible API endpoint (required for generic provider)",
    ),
    verbose: bool = typer.Option(
        False,
        "-v",
        "--verbose",
        help="Enable verbose output",
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
    exclude: Optional[list[str]] = typer.Option(
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
        help="Log all LLM input/output to .skene/debug/",
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
    # Load config with fallbacks
    config = load_config()

    # Apply config defaults
    resolved_api_key = api_key or config.api_key
    resolved_provider = provider or config.provider
    resolved_base_url = base_url or config.base_url
    if model:
        resolved_model = model
    else:
        resolved_model = config.get("model") or default_model_for_provider(resolved_provider)

    # Handle output path: if it's a directory, append default filename
    if output:
        # Resolve to absolute path
        if output.is_absolute():
            resolved_output = output.resolve()
        else:
            resolved_output = (Path.cwd() / output).resolve()

        # If path exists and is a directory, or has no file extension, append default filename
        if resolved_output.exists() and resolved_output.is_dir():
            # Path exists and is a directory, append default filename
            resolved_output = (resolved_output / "growth-manifest.json").resolve()
        elif not resolved_output.suffix:
            # No file extension provided, treat as directory and append filename
            resolved_output = (resolved_output / "growth-manifest.json").resolve()
        else:
            # Ensure final path is absolute
            resolved_output = resolved_output.resolve()
    else:
        resolved_output = Path(config.output_dir) / "growth-manifest.json"

    # LM Studio and Ollama don't require an API key (local servers)
    is_local_provider = resolved_provider.lower() in (
        "lmstudio",
        "lm-studio",
        "lm_studio",
        "ollama",
        "generic",
        "openai-compatible",
        "openai_compatible",
    )

    # Generic provider requires base_url
    if resolved_provider.lower() in ("generic", "openai-compatible", "openai_compatible"):
        if not resolved_base_url:
            console.print("[red]Error:[/red] The 'generic' provider requires --base-url to be set.")
            raise typer.Exit(1)

    # If no API key and not using local provider, show sample report or require key
    if not resolved_api_key and not is_local_provider:
        if features:
            console.print(
                "[yellow]No API key provided.[/yellow] Feature analysis requires an LLM.\n"
                "Set --api-key, SKENE_API_KEY env var, or add to .skene.config"
            )
            raise typer.Exit(1)
        console.print(
            "[yellow]No API key provided.[/yellow] Showing sample growth analysis preview.\n"
            "For full AI-powered analysis, set --api-key, SKENE_API_KEY env var, or add to .skene.config\n"
        )
        show_sample_report(path, output, exclude_folders=exclude if exclude else None)
        return

    if not resolved_api_key:
        if is_local_provider:
            resolved_api_key = resolved_provider  # Dummy key for local server

    # If features only, use features mode
    mode_str = "docs" if product_docs else ("features" if features else "growth")
    console.print(
        Panel.fit(
            f"[bold blue]Analyzing codebase[/bold blue]\n"
            f"Path: {path}\n"
            f"Provider: {resolved_provider}\n"
            f"Model: {resolved_model}\n"
            f"Mode: {mode_str}",
            title="skene",
        )
    )

    # Collect exclude folders from config and CLI
    exclude_folders = list(config.exclude_folders) if config.exclude_folders else []
    if exclude:
        # Merge CLI excludes with config excludes (deduplicate)
        exclude_folders = list(set(exclude_folders + exclude))

    # Resolve debug flag (CLI overrides config)
    resolved_debug = debug or config.debug

    # Run async analysis - execute and handle output

    from skene.llm import create_llm_client

    async def execute_analysis():
        # Create LLM client once and reuse it
        llm = create_llm_client(
            resolved_provider,
            SecretStr(resolved_api_key),
            resolved_model,
            base_url=resolved_base_url,
            debug=resolved_debug,
            no_fallback=no_fallback,
        )

        if features:
            result, manifest_data = await run_features_analysis(
                path,
                resolved_output,
                llm,
                verbose,
                exclude_folders=exclude_folders if exclude_folders else None,
            )
            registry_path = resolved_output.parent / "feature-registry.json"
            if result is None:
                raise typer.Exit(1)
            console.print(f"\n[green]Success![/green] Feature registry updated: {registry_path}")
            if manifest_data:
                show_features_summary(manifest_data)
        else:
            result, manifest_data = await run_analysis(
                path,
                resolved_output,
                llm,
                verbose,
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

            # Show summary
            console.print(f"\n[green]Success![/green] Manifest saved to: {resolved_output}")

            # Show quick stats if available
            if result.data:
                show_analysis_summary(result.data, template_data)

    asyncio.run(execute_analysis())


@app.command(deprecated=True, hidden=True)
def generate(
    manifest: Optional[Path] = typer.Option(
        None,
        "-m",
        "--manifest",
        help="Path to growth-manifest.json (auto-detected if not specified)",
    ),
    output_dir: Path = typer.Option(
        "./skene-docs",
        "-o",
        "--output",
        help="Output directory for generated documentation",
    ),
):
    """
    [DEPRECATED] Use 'analyze --product-docs' instead.

    This command has been consolidated into the analyze command.
    """
    console.print(
        "[yellow]Warning:[/yellow] The 'generate' command is deprecated.\n"
        "Use 'skene analyze --product-docs' instead.\n"
        "This command will be removed in v0.2.0."
    )
    raise typer.Exit(1)


@app.command()
def plan(
    manifest: Optional[Path] = typer.Option(
        None,
        "--manifest",
        help="Path to growth-manifest.json",
    ),
    template: Optional[Path] = typer.Option(
        None,
        "--template",
        help="Path to growth-template.json",
    ),
    context: Optional[Path] = typer.Option(
        None,
        "--context",
        "-c",
        help="Directory containing growth-manifest.json and growth-template.json (auto-detected if not specified)",
    ),
    output: Path = typer.Option(
        "./skene-context/growth-plan.md",
        "-o",
        "--output",
        help="Output path for growth plan (markdown)",
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        envvar="SKENE_API_KEY",
        help="API key for LLM provider (or set SKENE_API_KEY env var)",
    ),
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        "-p",
        help="LLM provider to use (openai, gemini, anthropic/claude, ollama)",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="LLM model name (e.g., gemini-3-flash-preview for v1beta API)",
    ),
    base_url: Optional[str] = typer.Option(
        None,
        "--base-url",
        envvar="SKENE_BASE_URL",
        help="Base URL for OpenAI-compatible API endpoint (required for generic provider)",
    ),
    verbose: bool = typer.Option(
        False,
        "-v",
        "--verbose",
        help="Enable verbose output",
    ),
    activation: bool = typer.Option(
        False,
        "--activation",
        help="Generate activation-focused plan using Senior Activation Engineer perspective",
    ),
    prompt: Optional[str] = typer.Option(
        None,
        "--prompt",
        help="Additional user prompt to influence the plan generation",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Log all LLM input/output to .skene/debug/",
    ),
    no_fallback: bool = typer.Option(
        False,
        "--no-fallback",
        help="Disable model fallback on rate limits; retry same model instead",
    ),
):
    """
    Generate a growth plan using Council of Growth Engineers.

    Uses manifest and template when present (auto-detected from
    ./skene-context/ or current dir) to generate a growth plan.
    None of these context files are required.

    Examples:

        # Generate growth plan (uses any context files found)
        uvx skene plan --api-key "your-key"
        # Or: uvx skene plan --api-key "your-key"

        # Specify context directory containing manifest and template
        uvx skene plan --context ./my-context --api-key "your-key"

        # Override context file paths
        uvx skene plan --manifest ./skene-context/growth-manifest.json --template ./skene-context/growth-template.json

        # Generate activation-focused plan
        uvx skene plan --activation --api-key "your-key"

        # Generate plan with additional user context
        uvx skene plan --prompt "Focus on enterprise customers" --api-key "your-key"
    """
    # Load config with fallbacks
    config = load_config()

    # Apply config defaults
    resolved_api_key = api_key or config.api_key
    resolved_provider = provider or config.provider
    resolved_base_url = base_url or config.base_url
    if model:
        resolved_model = model
    else:
        resolved_model = config.get("model") or default_model_for_provider(resolved_provider)

    # Validate context directory if provided
    if context:
        if not context.exists():
            console.print(f"[red]Error:[/red] Context directory does not exist: {context}")
            raise typer.Exit(1)
        if not context.is_dir():
            console.print(f"[red]Error:[/red] Context path is not a directory: {context}")
            raise typer.Exit(1)

    # Auto-detect manifest (growth-manifest.json is the standard name from analyze)
    if manifest is None:
        default_paths = []

        # If context is specified, check there first
        if context:
            default_paths.append(context / "growth-manifest.json")

        # Then check standard default paths
        default_paths.extend(
            [
                Path("./skene-context/growth-manifest.json"),
                Path("./growth-manifest.json"),
            ]
        )

        for p in default_paths:
            if p.exists():
                manifest = p
                break

    # Auto-detect template
    if template is None:
        default_template_paths = []

        # If context is specified, check there first
        if context:
            default_template_paths.append(context / "growth-template.json")

        # Then check standard default paths
        default_template_paths.extend(
            [
                Path("./skene-context/growth-template.json"),
                Path("./growth-template.json"),
            ]
        )

        for p in default_template_paths:
            if p.exists():
                template = p
                break

    # Check API key
    is_local_provider = resolved_provider.lower() in (
        "lmstudio",
        "lm-studio",
        "lm_studio",
        "ollama",
        "generic",
        "openai-compatible",
        "openai_compatible",
    )

    # Generic provider requires base_url
    if resolved_provider.lower() in ("generic", "openai-compatible", "openai_compatible"):
        if not resolved_base_url:
            console.print("[red]Error:[/red] The 'generic' provider requires --base-url to be set.")
            raise typer.Exit(1)

    # If no API key and not using local provider, show sample report
    if not resolved_api_key and not is_local_provider:
        # Determine path for sample report (use context dir if provided, else current dir)
        sample_path = context if context else Path(".")
        console.print(
            "[yellow]No API key provided.[/yellow] Showing sample growth plan preview.\n"
            "For full AI-powered plan generation, set --api-key, SKENE_API_KEY env var, "
            "or add to .skene.config\n"
        )
        show_sample_report(sample_path, output, exclude_folders=None)
        return

    if not resolved_api_key:
        resolved_api_key = resolved_provider  # Dummy key for local server

    # Handle output path: if it's a directory, append default filename
    # Resolve to absolute path
    if output.is_absolute():
        resolved_output = output.resolve()
    else:
        resolved_output = (Path.cwd() / output).resolve()

    # If path exists and is a directory, or has no file extension, append default filename
    if resolved_output.exists() and resolved_output.is_dir():
        # Path exists and is a directory, append default filename
        resolved_output = (resolved_output / "growth-plan.md").resolve()
    elif not resolved_output.suffix:
        # No file extension provided, treat as directory and append filename
        resolved_output = (resolved_output / "growth-plan.md").resolve()

    # Ensure final path is absolute (should already be, but double-check)
    resolved_output = resolved_output.resolve()

    plan_type = "activation plan" if activation else "growth plan"
    base = context if context else Path(".")
    default_manifest = (
        (base / "skene-context" / "growth-manifest.json") if not context else (base / "growth-manifest.json")
    )
    default_template = (
        (base / "skene-context" / "growth-template.json") if not context else (base / "growth-template.json")
    )
    manifest_display = str(manifest.resolve()) if manifest else f"{default_manifest.resolve()} (not found)"
    template_display = str(template.resolve()) if template else f"{default_template.resolve()} (not found)"

    # Determine context directory for growth-loops and plan-steps
    context_dir_for_loops = None
    if context:
        context_dir_for_loops = context
    elif manifest:
        # If manifest is in skene-context, use that parent
        if manifest.parent.name == "skene-context":
            context_dir_for_loops = manifest.parent
    elif resolved_output:
        # If output is in skene-context, use that parent
        if resolved_output.parent.name == "skene-context":
            context_dir_for_loops = resolved_output.parent
        else:
            # Check if skene-context exists in same directory as output
            potential_context = resolved_output.parent / "skene-context"
            if potential_context.exists():
                context_dir_for_loops = potential_context

    # Base dir for plan-steps (same logic as run_generate_plan)
    base_dir_for_steps = context_dir_for_loops
    if base_dir_for_steps is None and manifest:
        mp = manifest.parent
        skene_ctx = mp / "skene-context"
        base_dir_for_steps = mp if mp.name == "skene-context" else (skene_ctx if skene_ctx.exists() else mp)
    elif base_dir_for_steps is None and resolved_output:
        base_dir_for_steps = (
            resolved_output.parent
            if resolved_output.parent.name == "skene-context"
            else (
                resolved_output.parent / "skene-context"
                if (resolved_output.parent / "skene-context").exists()
                else resolved_output.parent
            )
        )
    elif base_dir_for_steps is None:
        base_dir_for_steps = Path(".")

    plan_steps_path = find_plan_steps_path(base_dir_for_steps)
    plan_steps_display = str(plan_steps_path) if plan_steps_path else None

    panel_lines = [
        f"[bold blue]Generating {plan_type}[/bold blue]",
        f"Manifest: {manifest_display}",
        f"Template: {template_display}",
        f"Output: {resolved_output}",
        f"Provider: {resolved_provider}",
        f"Model: {resolved_model}",
    ]
    if plan_steps_display:
        panel_lines.insert(1, f"Plan steps: {plan_steps_display}")

    console.print(Panel.fit("\n".join(panel_lines), title="skene"))

    # Resolve debug flag (CLI overrides config)
    resolved_debug = debug or config.debug

    # Run async cycle generation - execute and handle output
    async def execute_cycle():
        memo_content, todo_data = await run_generate_plan(
            manifest_path=manifest,
            template_path=template,
            output_path=resolved_output,
            api_key=resolved_api_key,
            provider=resolved_provider,
            model=resolved_model,
            verbose=verbose,
            activation=activation,
            context_dir=context_dir_for_loops,
            user_prompt=prompt,
            debug=resolved_debug,
            base_url=resolved_base_url,
            no_fallback=no_fallback,
        )

        if memo_content is None:
            raise typer.Exit(1)

        console.print(f"\n[green]Success![/green] Growth plan saved to: {resolved_output}")

    asyncio.run(execute_cycle())


@app.command(rich_help_panel="experimental")
def chat(
    path: Path = typer.Argument(
        ".",
        help="Path to codebase to analyze",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        envvar="SKENE_API_KEY",
        help="API key for LLM provider (or set SKENE_API_KEY env var)",
    ),
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        "-p",
        help="LLM provider to use (openai, gemini, anthropic/claude, ollama)",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="LLM model name (e.g., gemini-3-flash-preview for v1beta API)",
    ),
    base_url: Optional[str] = typer.Option(
        None,
        "--base-url",
        envvar="SKENE_BASE_URL",
        help="Base URL for OpenAI-compatible API endpoint (required for generic provider)",
    ),
    max_steps: int = typer.Option(
        4,
        "--max-steps",
        help="Maximum tool calls per user request",
    ),
    tool_output_limit: int = typer.Option(
        4000,
        "--tool-output-limit",
        help="Max tool output characters kept in context",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Log all LLM input/output to .skene/debug/",
    ),
):
    """
    Interactive terminal chat that invokes skene tools.

    Examples:

        uvx skene chat . --api-key "your-key"
        # Or: uvx skene chat . --api-key "your-key"
        uvx skene chat ./my-project --provider gemini --model gemini-3-flash-preview
    """
    config = load_config()

    resolved_api_key = api_key or config.api_key
    resolved_provider = provider or config.provider
    resolved_base_url = base_url or config.base_url
    if model:
        resolved_model = model
    else:
        resolved_model = config.get("model") or default_model_for_provider(resolved_provider)

    is_local_provider = resolved_provider.lower() in (
        "lmstudio",
        "lm-studio",
        "lm_studio",
        "ollama",
        "generic",
        "openai-compatible",
        "openai_compatible",
    )

    # Generic provider requires base_url
    if resolved_provider.lower() in ("generic", "openai-compatible", "openai_compatible"):
        if not resolved_base_url:
            console.print("[red]Error:[/red] The 'generic' provider requires --base-url to be set.")
            raise typer.Exit(1)

    if not resolved_api_key:
        if is_local_provider:
            resolved_api_key = resolved_provider
        else:
            console.print(
                "[yellow]Warning:[/yellow] No API key provided. "
                "Set --api-key, SKENE_API_KEY env var, or add to .skene.config"
            )
            raise typer.Exit(1)

    # Resolve debug flag (CLI overrides config)
    resolved_debug = debug or config.debug

    from skene.cli.chat import run_chat

    run_chat(
        console=console,
        repo_path=path,
        api_key=resolved_api_key,
        provider=resolved_provider,
        model=resolved_model,
        max_steps=max_steps,
        tool_output_limit=tool_output_limit,
        debug=resolved_debug,
        base_url=resolved_base_url,
    )


@app.command(rich_help_panel="manage")
def validate(
    manifest: Path = typer.Argument(
        ...,
        help="Path to growth-manifest.json to validate",
        exists=True,
    ),
):
    """
    Validate a growth-manifest.json against the schema.

    Checks that the manifest file is valid JSON and conforms
    to the GrowthManifest schema.

    Examples:

        uvx skene validate ./growth-manifest.json
        # Or: uvx skene validate ./growth-manifest.json
    """
    console.print(f"Validating: {manifest}")

    try:
        # Load JSON
        data = json.loads(manifest.read_text())

        # Validate against schema
        from skene.manifest import GrowthManifest

        manifest_obj = GrowthManifest(**data)

        console.print("[green]Valid![/green] Manifest conforms to schema.")

        # Show summary
        table = Table(title="Manifest Summary")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Project", manifest_obj.project_name)
        table.add_row("Version", manifest_obj.version)
        table.add_row("Tech Stack", manifest_obj.tech_stack.language or "Unknown")
        table.add_row("Current Growth Features", str(len(manifest_obj.current_growth_features)))
        table.add_row("New Growth Opportunities", str(len(manifest_obj.growth_opportunities)))

        console.print(table)

    except json.JSONDecodeError as e:
        console.print(f"[red]Invalid JSON:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Validation failed:[/red] {e}")
        raise typer.Exit(1)


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
    context: Optional[Path] = typer.Option(
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
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        envvar="SKENE_API_KEY",
        help="API key for LLM provider (required for --find-alternatives)",
    ),
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        "-p",
        help="LLM provider: openai, gemini, anthropic, ollama (uses config if not provided)",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="LLM model (uses provider default if not provided)",
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
            console.print(
                "[red]Could not find skene-context/growth-loops/ directory.[/red]\n"
                "Use --context to specify the path explicitly."
            )
            raise typer.Exit(1)

    loops_dir = context / "growth-loops"
    if not loops_dir.is_dir():
        console.print(f"[red]Growth loops directory not found:[/red] {loops_dir}")
        raise typer.Exit(1)

    # Setup LLM client if find_alternatives is enabled
    llm_client = None
    if find_alternatives:
        from skene.config import load_config
        from skene.llm.factory import create_llm_client

        config = load_config()
        resolved_api_key = api_key or config.api_key
        resolved_provider = provider or config.provider
        resolved_model = model or config.model

        if not resolved_api_key:
            console.print(
                "[yellow]Warning:[/yellow] --find-alternatives requires an API key.\n"
                "Provide --api-key or set SKENE_API_KEY environment variable."
            )
            raise typer.Exit(1)

        try:
            llm_client = create_llm_client(
                provider=resolved_provider,
                api_key=SecretStr(resolved_api_key),
                model_name=resolved_model,
            )
            console.print("[dim]💡 Semantic matching enabled (finding alternative implementations)[/dim]")
        except Exception as exc:
            console.print(f"[red]Failed to initialize LLM client:[/red] {exc}")
            raise typer.Exit(1)

    console.print(f"[dim]Project root:[/dim] {path}")
    console.print(f"[dim]Context dir:[/dim]  {context}")
    console.print(f"[dim]Loops dir:[/dim]    {loops_dir}")
    console.print()

    # Register event listener for simple text output
    def event_listener(event: ValidationEvent, payload: dict[str, Any]) -> None:
        """Display validation events as simple text messages."""
        if event == ValidationEvent.LOOP_VALIDATION_STARTED:
            loop_name = payload.get("loop_name", "Unknown Loop")
            console.print(f"Validating {loop_name}...")
        elif event == ValidationEvent.REQUIREMENT_MET:
            req_type = payload.get("type", "")
            if req_type == "file":
                file_path = payload.get("path", "")
                console.print(f"  File requirement met: {file_path}...")
            elif req_type == "function":
                func_name = payload.get("name", "")
                console.print(f"  Function requirement met: {func_name}...")
        elif event == ValidationEvent.LOOP_COMPLETED:
            loop_name = payload.get("loop_name", "Unknown Loop")
            console.print(f"Loop complete: {loop_name}...")
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


@app.command(rich_help_panel="manage")
def login(
    upstream: Optional[str] = typer.Option(
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

    if init:
        written = ensure_base_schema_migration(path.resolve())
        console.print(f"[green]Schema migration:[/green] {written}")
        console.print("[dim]Run supabase db push to apply.[/dim]")
        return

    if ingest_url and not local:
        console.print("[red]--ingest-url can only be used with --local.[/red]")
        raise typer.Exit(1)
    if local and upstream:
        console.print("[red]--local and --upstream cannot be used together.[/red]")
        raise typer.Exit(1)
    if local and push_only:
        console.print("[red]--local and --push-only cannot be used together.[/red]")
        raise typer.Exit(1)

    config = load_config()
    resolved_upstream = None if local else (upstream or config.upstream)
    resolved_token = resolve_upstream_token(config) if resolved_upstream else None

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
            console.print(
                "[red]Could not find skene-context/growth-loops/ directory.[/red]\n"
                "Use --context to specify the path explicitly."
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
                    console.print(f"[red]No loop with loop_id '{loop_id}' has Supabase telemetry.[/red]")
                    raise typer.Exit(1)
        if not loops_with_telemetry and not local:
            console.print(
                "[yellow]No growth loops with Supabase telemetry found.[/yellow]\n"
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
        console.print("[dim]Building migration files with default Skene.ai upstream ingest for reference.[/dim]")
        console.print(
            "[dim]For self-hosted trigger ingests, use: "
            "[bold]skene push --local --ingest-url https://your-ingest.example.com[/bold].[/dim]"
        )
        console.print("[dim]To push to upstream managed by Skene.ai, use [bold]skene login[/bold].[/dim]")

    try:
        schema_path = ensure_base_schema_migration(path)
        console.print(f"[green]Schema:[/green] {schema_path}")

        if not push_only:
            migration_path = build_loops_to_supabase(
                loops_with_telemetry,
                path,
                forward_url=forward_url,
                proxy_secret=secret,
            )
            console.print(f"[green]Telemetry:[/green] {migration_path}")
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
                        console.print(f"[green]Telemetry:[/green] {telemetry}")
                if (ctx / "growth-loops").is_dir():
                    console.print(f"[green]Growth loops:[/green] {ctx / 'growth-loops'}")
            if not resolved_token:
                console.print("[yellow]No token. Run skene login to authenticate.[/yellow]")
            else:
                loops_dir = ctx / "growth-loops" if ctx.exists() else None
                if loops_dir and loops_dir.exists():
                    console.print(f"[green]Growth loops:[/green] {loops_dir}")
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
                    console.print(
                        f"[green]Pushed to upstream[/green] commit_hash={result.get('commit_hash', '?')} "
                        f"(package: {', '.join(sent_parts)})"
                    )
                else:
                    msg = result.get("message", "Push failed.")
                    if result.get("error") == "auth":
                        console.print(f"[red]{msg}[/red]")
                    else:
                        console.print(f"[yellow]{msg}[/yellow]")

        if not push_only and resolved_upstream:
            console.print("\n[dim]Upstream parses the package (growth loops + telemetry.sql) and deploys.[/dim]\n")
    except Exception as e:
        console.print(f"[red]Deploy failed:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def build(
    plan: Optional[Path] = typer.Option(
        None,
        "--plan",
        help="Path to growth plan markdown file",
    ),
    context: Optional[Path] = typer.Option(
        None,
        "--context",
        "-c",
        help="Directory containing growth-plan.md (auto-detected if not specified)",
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        envvar="SKENE_API_KEY",
        help="API key for LLM (uses config if not provided)",
    ),
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        "-p",
        help="LLM provider: openai, gemini, anthropic, ollama (uses config if not provided)",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="LLM model (uses provider default if not provided)",
    ),
    base_url: Optional[str] = typer.Option(
        None,
        "--base-url",
        envvar="SKENE_BASE_URL",
        help="Base URL for OpenAI-compatible API endpoint (required for generic provider)",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Log all LLM input/output to .skene/debug/",
    ),
    no_fallback: bool = typer.Option(
        False,
        "--no-fallback",
        help="Disable model fallback on rate limits; retry same model instead",
    ),
    target: Optional[str] = typer.Option(
        None,
        "--target",
        "-t",
        help="Where to send the prompt (skip interactive menu). Options: cursor, claude, show, file",
    ),
    feature: Optional[str] = typer.Option(
        None,
        "--feature",
        "-f",
        help="Bias toward this feature name when linking the loop",
    ),
):
    """
    Build an AI prompt from your growth plan using LLM, then choose where to send it.

    Workflow:
    1. Extracts Technical Execution from growth plan
    2. Builds and saves growth loop definition (Supabase telemetry)
    3. Asks where to send: Cursor, Claude, or Show
    4. Generates implementation prompt with LLM and executes

    Use --target to skip the interactive menu (useful for scripting):

        skene build --target file    # Just save prompt to file, no interaction
        skene build --target show    # Print prompt to stdout
        skene build --target cursor  # Open in Cursor
        skene build --target claude  # Open in Claude

    Examples:

        # Uses config for LLM, then asks where to send
        skene build

        # Non-interactive: just generate and save the prompt file
        skene build --target file

        # Override LLM settings from config
        skene build --api-key "your-key" --provider gemini

        # Custom model
        skene build --provider anthropic --model claude-sonnet-4

        # Specify custom plan location
        skene build --plan ./my-plan.md

    Configuration:
        Set api_key and provider in .skene.config or ~/.config/skene/config
    """
    # Validate --target value if provided
    valid_targets = {"cursor", "claude", "show", "file"}
    if target is not None and target not in valid_targets:
        console.print(f"[red]Error:[/red] Invalid target '{target}'. Valid options: {', '.join(sorted(valid_targets))}")
        raise typer.Exit(1)

    # Run async logic
    asyncio.run(_build_async(plan, context, api_key, provider, model, debug, target, base_url, no_fallback, feature))


async def _build_async(
    plan: Optional[Path],
    context: Optional[Path],
    api_key: Optional[str],
    provider: Optional[str],
    model: Optional[str],
    debug: bool = False,
    target: Optional[str] = None,
    base_url: Optional[str] = None,
    no_fallback: Optional[bool] = False,
    bias_feature: Optional[str] = None,
):
    """Async implementation of build command."""
    # Load config to get LLM settings
    config = load_config()
    api_key = api_key or config.api_key
    provider = provider or config.provider
    base_url = base_url or config.base_url

    # Generic provider requires base_url
    if provider and provider.lower() in ("generic", "openai-compatible", "openai_compatible"):
        if not base_url:
            console.print("[red]Error:[/red] The 'generic' provider requires --base-url to be set.")
            raise typer.Exit(1)

    # Validate LLM configuration
    if not api_key or not provider:
        console.print(
            "[red]Error:[/red] LLM configuration required.\n\n"
            "Please set api_key and provider in one of:\n"
            "  1. .skene.config (in current directory)\n"
            "  2. ~/.config/skene/config\n"
            "  3. Command options: --api-key and --provider\n"
            "  4. Environment: SKENE_API_KEY\n\n"
            "Example config:\n"
            '  api_key = "your-api-key"\n'
            '  provider = "gemini"  # or anthropic, openai, ollama\n'
        )
        raise typer.Exit(1)
    # Auto-detect plan file
    if plan is None:
        default_paths = []

        # If context is specified, check there first
        if context:
            if not context.exists():
                console.print(f"[red]Error:[/red] Context directory does not exist: {context}")
                raise typer.Exit(1)
            if not context.is_dir():
                console.print(f"[red]Error:[/red] Context path is not a directory: {context}")
                raise typer.Exit(1)
            default_paths.append(context / "growth-plan.md")

        # Then check standard default paths
        default_paths.extend(
            [
                Path("./skene-context/growth-plan.md"),
                Path("./growth-plan.md"),
            ]
        )

        for p in default_paths:
            if p.exists():
                plan = p
                break

    # Validate plan file exists
    if plan is None or not plan.exists():
        console.print(
            "[red]Error:[/red] Growth plan not found.\n\n"
            "Please ensure a growth plan exists at one of:\n"
            "  - ./skene-context/growth-plan.md (default)\n"
            "  - ./growth-plan.md\n"
            "  - Or specify a custom path with --plan\n\n"
            "Generate a plan first with: [cyan]skene plan[/cyan]"
        )
        raise typer.Exit(1)

    # Extract Technical Execution section from JSON
    technical_execution = extract_technical_execution(plan)

    if not technical_execution:
        console.print(
            "[red]Error:[/red] Could not extract Technical Execution section from growth plan.\n"
            "Please ensure a growth-plan.json file exists alongside your growth-plan.md.\n"
            "Re-generate the plan with: [cyan]skene plan[/cyan]\n"
        )
        raise typer.Exit(1)

    # Create LLM client and generate prompt
    if model is None:
        model = config.get("model") or default_model_for_provider(provider)

    try:
        from pydantic import SecretStr

        from skene.llm import create_llm_client

        resolved_debug = debug or config.debug
        llm = create_llm_client(
            provider, SecretStr(api_key), model, base_url=base_url, debug=resolved_debug, no_fallback=no_fallback
        )
        console.print("")
        console.print(f"[dim]Using {provider} ({model})[/dim]\n")
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to create LLM client: {e}")
        raise typer.Exit(1)

    # Display the technical execution context
    console.print(f"[bold blue]Technical Execution:[/bold blue] {plan}\n")
    if technical_execution.get("next_build"):
        console.print(
            Panel(
                technical_execution["next_build"],
                title="[bold cyan]The Next Build[/bold cyan]",
                border_style="cyan",
                padding=(1, 2),
            )
        )

    # Run loop in: always Supabase for now (Skene Cloud option disabled)
    run_target = "supabase"

    # 2. Loop build
    try:
        from skene.growth_loops.storage import (
            derive_loop_id,
            derive_loop_name,
            generate_loop_definition_with_llm,
            generate_timestamped_filename,
            write_growth_loop_json,
        )

        # Derive initial loop metadata (will be refined after LLM generation)
        loop_name = derive_loop_name(technical_execution)
        loop_id = derive_loop_id(loop_name)

        # Determine base output directory
        if context and context.exists():
            base_output_dir = context
        else:
            base_output_dir = Path(config.output_dir)

        from skene.feature_registry import load_features_for_build

        features = load_features_for_build(base_output_dir)

        # Generate loop definition with LLM (telemetry format depends on run_target)
        console.print("\n[dim]Please wait...Generating growth loop definition...[/dim]")
        console.print("")
        loop_definition = await generate_loop_definition_with_llm(
            llm=llm,
            technical_execution=technical_execution,
            plan_path=plan.resolve(),
            codebase_path=Path.cwd(),
            run_target=run_target,
            features=features if features else None,
            bias_feature_name=bias_feature,
        )

        # Extract loop_id and name from generated definition (in case LLM changed them)
        loop_id = loop_definition.get("loop_id", loop_id)
        loop_name = loop_definition.get("name", loop_name)

        # Generate filename using final loop_id
        timestamped_filename = generate_timestamped_filename(loop_id)

        loop_definition["run_target"] = run_target
        loop_definition["_metadata"] = {
            "source_plan_path": str(plan.resolve()),
            "saved_at": datetime.now().isoformat(),
            "run_target": run_target,
        }

        # Write to file
        saved_path = write_growth_loop_json(
            base_dir=base_output_dir,
            filename=timestamped_filename,
            payload=loop_definition,
        )

        console.print(f"[dim]Saved growth loop to: {saved_path}[/dim]\n")

    except Exception as e:
        # Don't fail the whole build if storage fails
        console.print(f"[yellow]Warning:[/yellow] Failed to save growth loop: {e}")
        if config.verbose:
            import traceback

            console.print(traceback.format_exc())

    # 3. Ask build location (where to send the prompt)
    # If --target was provided, skip the interactive menu
    if target is None:
        # Interactive mode: ask where to send the prompt
        console.print("[bold cyan]Where do you want to send the implementation prompt?[/bold cyan]")
        try:
            import questionary

            choices_list = [
                questionary.Choice("Cursor (open via deep link)", value="cursor"),
                questionary.Choice("Claude (open in terminal)", value="claude"),
                questionary.Choice("Show full prompt", value="show"),
                questionary.Choice("Cancel", value="cancel"),
            ]
            selection = questionary.select(
                "",
                choices=choices_list,
                use_arrow_keys=True,
                use_shortcuts=True,
                instruction="(Use arrow keys to navigate, Enter to select)",
            ).ask()

            if selection == "cancel" or selection is None:
                console.print("\n[dim]Cancelled.[/dim]")
                return
            target = selection
        except ImportError:
            choices = [
                "1. Cursor (open via deep link)",
                "2. Claude (open in terminal)",
                "3. Show full prompt",
                "4. Cancel",
            ]
            for choice in choices:
                console.print(f"  {choice}")
            console.print()
            selection = Prompt.ask("Select option", choices=["1", "2", "3", "4"], default="1")
            if selection == "1":
                target = "cursor"
            elif selection == "2":
                target = "claude"
            elif selection == "3":
                target = "show"
            elif selection == "4":
                console.print("[dim]Cancelled.[/dim]")
                return
            else:
                target = "cursor"

    # 4. Prompt build
    console.print("\n[dim]Generating implementation prompt...[/dim]\n")
    try:
        prompt = await build_prompt_with_llm(plan.resolve(), technical_execution, llm)
    except Exception as e:
        console.print(f"[yellow]Warning:[/yellow] LLM prompt generation failed: {e}")
        console.print("[dim]Falling back to template...[/dim]\n")
        prompt = build_prompt_from_template(plan.resolve(), technical_execution)

    # Save prompt to a file for cross-platform consumption
    prompt_output_dir = plan.parent if plan else Path(config.output_dir)
    prompt_file = save_prompt_to_file(prompt, prompt_output_dir)
    console.print(f"[dim]Prompt saved to: {prompt_file}[/dim]")

    # Execute based on target
    if target == "file":
        # Non-interactive: just save the prompt file and exit
        console.print(f"\n[green]✓[/green] Prompt saved to: {prompt_file}")

    elif target == "show":
        console.print("\n")
        console.print(Panel(prompt, title="[bold]Full Prompt[/bold]", border_style="blue", padding=(1, 2)))
        console.print(f"\n[green]✓[/green] Prompt saved to: {prompt_file}")
        console.print("[dim]Copy and use as needed.[/dim]\n")

    elif target == "cursor":
        console.print("\n[dim]Opening Cursor with deep link...[/dim]")
        try:
            open_cursor_deeplink(prompt_file, project_root=Path.cwd())
            console.print("[green]Success![/green] Cursor should now open with your prompt.")
            console.print(f"[dim]Prompt file: {prompt_file}[/dim]\n")
        except RuntimeError as e:
            console.print(f"\n[red]Error:[/red] {e}\n")
            console.print(f"[yellow]Prompt saved to:[/yellow] {prompt_file}")
            console.print("[dim]You can open this file in Cursor manually.[/dim]\n")
            raise typer.Exit(1)

    elif target == "claude":
        console.print("\n[dim]Launching Claude...[/dim]\n")
        try:
            run_claude(prompt_file)
        except RuntimeError as e:
            console.print(f"\n[red]Error:[/red] {e}\n")
            console.print(f"[yellow]Prompt saved to:[/yellow] {prompt_file}")
            console.print("[dim]You can run Claude manually with the saved prompt file.[/dim]\n")
            raise typer.Exit(1)


app.add_typer(features_app, name="features", rich_help_panel="manage")


@app.command(rich_help_panel="manage")
def config(
    init: bool = typer.Option(
        False,
        "--init",
        help="Create a sample config file in current directory",
    ),
    show: bool = typer.Option(
        False,
        "--show",
        help="Show current configuration values",
    ),
):
    """
    Manage skene configuration.

    Configuration files are loaded in this order (later overrides earlier):
    1. User config: ~/.config/skene/config
    2. Project config: ./.skene.config
    3. Environment variables (SKENE_API_KEY, SKENE_PROVIDER)
    4. CLI arguments

    Examples:

        # Show current configuration
        uvx skene config --show
        # Or: uvx skene config --show

        # Create a sample config file
        uvx skene config --init
        # Or: uvx skene config --init
    """
    from skene.config import find_project_config, find_user_config, load_config

    if init:
        config_path = Path(".skene.config")
        if config_path.exists():
            console.print(f"[yellow]Config already exists:[/yellow] {config_path}")
            raise typer.Exit(1)

        create_sample_config(config_path)
        console.print(f"[green]Created config file:[/green] {config_path}")
        console.print("\nEdit this file to add your API key and customize settings.")
        return

    # Default: show configuration
    cfg = load_config()
    project_cfg = find_project_config()
    user_cfg = find_user_config()

    show_config_status(cfg, project_cfg, user_cfg)

    if not project_cfg and not user_cfg:
        console.print("\n[dim]Tip: Run 'skene config --init' to create a config file[/dim]")
        return

    # Ask if user wants to edit
    console.print()
    edit = Confirm.ask("[bold yellow]Do you want to edit this configuration?[/bold yellow]", default=False)

    if not edit:
        return

    # Interactive configuration setup
    config_path, selected_provider, selected_model, new_api_key, base_url = interactive_config_setup()

    # Save configuration
    try:
        save_config(config_path, selected_provider, selected_model, new_api_key, base_url)
        console.print(f"\n[green]✓ Configuration saved to:[/green] {config_path}")
        console.print(f"[green]  Provider:[/green] {selected_provider}")
        console.print(f"[green]  Model:[/green] {selected_model}")
        if base_url:
            console.print(f"[green]  Base URL:[/green] {base_url}")
        console.print(f"[green]  API Key:[/green] {'Set' if new_api_key else 'Not set'}")
    except Exception as e:
        console.print(f"[red]Error saving configuration:[/red] {e}")
        raise typer.Exit(1)


def _run_chat_default(
    path: Path = typer.Argument(
        ".",
        help="Path to codebase to analyze",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        envvar="SKENE_API_KEY",
        help="API key for LLM provider (or set SKENE_API_KEY env var)",
    ),
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        "-p",
        help="LLM provider to use (openai, gemini, anthropic/claude, ollama)",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="LLM model name (e.g., gemini-3-flash-preview for v1beta API)",
    ),
    max_steps: int = typer.Option(
        4,
        "--max-steps",
        help="Maximum tool calls per user request",
    ),
    tool_output_limit: int = typer.Option(
        4000,
        "--tool-output-limit",
        help="Max tool output characters kept in context",
    ),
):
    """Interactive terminal chat that invokes skene tools."""
    # Auto-create user config on first run if no config exists
    from skene.config import find_project_config, find_user_config

    user_cfg = find_user_config()
    project_cfg = find_project_config()

    if not user_cfg and not project_cfg:
        # Create user config directory if it doesn't exist
        config_home = os.environ.get("XDG_CONFIG_HOME")
        if config_home:
            config_dir = Path(config_home) / "skene"
        else:
            config_dir = Path.home() / ".config" / "skene"

        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "config"

        # Create sample config
        create_sample_config(config_path)
        console.print(
            f"[green]Created config file:[/green] {config_path}\n"
            "[dim]Edit this file to add your API key and customize settings.[/dim]\n"
        )

    config = load_config()

    resolved_api_key = api_key or config.api_key
    resolved_provider = provider or config.provider
    if model:
        resolved_model = model
    else:
        resolved_model = config.get("model") or default_model_for_provider(resolved_provider)

    is_local_provider = resolved_provider.lower() in (
        "lmstudio",
        "lm-studio",
        "lm_studio",
        "ollama",
    )

    if not resolved_api_key:
        if is_local_provider:
            resolved_api_key = resolved_provider
        else:
            # Find which config file exists to show helpful message
            config_file = find_project_config() or find_user_config()
            if config_file:
                console.print(
                    f"[yellow]Warning:[/yellow] No API key provided. "
                    "While that is ok, without api-key, Skene will not use advanced AI-analysis tools.\n"
                    f"To enable AI features, add your API key to: [cyan]{config_file}[/cyan]\n"
                    "Or set --api-key flag or SKENE_API_KEY env var."
                )
            else:
                console.print(
                    "[yellow]Warning:[/yellow] No API key provided. "
                    "While that is ok, without api-key, Skene will not use advanced AI-analysis tools.\n"
                    "To enable AI features, set --api-key, SKENE_API_KEY env var, or create a config file:\n"
                    "  ~/.config/skene/config (user-level)\n"
                    "  ./.skene.config (project-level)"
                )
            raise typer.Exit(1)

    from skene.cli.chat import run_chat

    run_chat(
        console=console,
        repo_path=path,
        api_key=resolved_api_key,
        provider=resolved_provider,
        model=resolved_model,
        max_steps=max_steps,
        tool_output_limit=tool_output_limit,
    )


def skene_entry_point():
    """Entry point for 'skene' command - includes all commands, defaults to chat."""
    # Create a typer app for the skene command that includes all commands
    skene_app = typer.Typer(
        name="skene",
        help="PLG analysis toolkit for codebases. Analyze code, detect growth opportunities.",
        add_completion=False,
        no_args_is_help=False,
        cls=SectionedHelpGroup,
    )

    # Add commands in order: analyze, plan, build, status, push | manage | experimental
    skene_app.command()(analyze)
    skene_app.command()(plan)
    skene_app.command()(build)
    skene_app.command()(status)
    skene_app.command()(push)
    skene_app.command(rich_help_panel="manage")(config)
    skene_app.command(rich_help_panel="manage")(validate)
    skene_app.command(rich_help_panel="manage")(login)
    skene_app.command(rich_help_panel="manage")(logout)
    skene_app.add_typer(features_app, name="features", rich_help_panel="manage")
    skene_app.command(rich_help_panel="experimental")(chat)

    # Add callback to handle default case (no subcommand) - launches chat
    # Added AFTER commands so subcommands take precedence
    # No arguments in callback to avoid conflicts with subcommands
    @skene_app.callback(invoke_without_command=True)
    def default_callback(
        ctx: typer.Context,
        version: bool = typer.Option(
            None,
            "--version",
            "-V",
            callback=version_callback,
            is_eager=True,
            help="Show version and exit.",
        ),
    ):
        """Default: Launch interactive chat. Use subcommands for other operations."""
        # Only invoke chat if no subcommand was provided
        if ctx.invoked_subcommand is None:
            # Parse all arguments manually from sys.argv
            import sys

            path_arg = "."
            api_key_arg = None
            provider_arg = None
            model_arg = None
            max_steps_arg = 4
            tool_output_limit_arg = 4000

            args = sys.argv[1:]  # Skip script name
            i = 0
            while i < len(args):
                arg = args[i]
                if arg in ["--api-key"] and i + 1 < len(args):
                    api_key_arg = args[i + 1]
                    i += 2
                elif arg in ["--provider", "-p"] and i + 1 < len(args):
                    provider_arg = args[i + 1]
                    i += 2
                elif arg in ["--model", "-m"] and i + 1 < len(args):
                    model_arg = args[i + 1]
                    i += 2
                elif arg == "--max-steps" and i + 1 < len(args):
                    max_steps_arg = int(args[i + 1])
                    i += 2
                elif arg == "--tool-output-limit" and i + 1 < len(args):
                    tool_output_limit_arg = int(args[i + 1])
                    i += 2
                elif arg.startswith("--api-key="):
                    api_key_arg = arg.split("=", 1)[1]
                    i += 1
                elif arg.startswith("--provider=") or arg.startswith("-p="):
                    provider_arg = arg.split("=", 1)[1]
                    i += 1
                elif arg.startswith("--model=") or arg.startswith("-m="):
                    model_arg = arg.split("=", 1)[1]
                    i += 1
                elif not arg.startswith("-"):
                    # Found a non-option argument - this is the path
                    path_arg = arg
                    i += 1
                else:
                    i += 1

            # Check environment variable for API key if not provided
            if not api_key_arg:
                api_key_arg = os.environ.get("SKENE_API_KEY")

            _run_chat_default(
                Path(path_arg),
                api_key_arg,
                provider_arg,
                model_arg,
                max_steps_arg,
                tool_output_limit_arg,
            )

    _run_cli(skene_app)


def skene_growth_entry():
    """Entry point for 'skene-growth' command (development). Use 'skene' for production."""
    _run_cli(app)


def skene_growth_mcp_entry():
    """Entry point for 'skene-growth-mcp' command (development). Use 'skene-mcp' for production."""
    from skene.mcp.server import main as mcp_main

    mcp_main()


if __name__ == "__main__":
    _run_cli(app)
