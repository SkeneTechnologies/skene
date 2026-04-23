"""Generate a growth plan using Council of Growth Engineers."""

import asyncio
from pathlib import Path

import typer
from rich.panel import Panel

from skene.cli.analysis_helpers import run_generate_plan
from skene.cli.app import app, resolve_cli_config
from skene.cli.sample_report import show_sample_report
from skene.output import console, error, success, warning
from skene.planner import find_plan_steps_path


@app.command()
def plan(
    manifest: Path | None = typer.Option(
        None,
        "--manifest",
        help="Path to growth-manifest.json",
    ),
    template: Path | None = typer.Option(
        None,
        "--template",
        help="Path to growth-template.json",
    ),
    context: Path | None = typer.Option(
        None,
        "--context",
        "-c",
        help="Directory containing growth-manifest.json and growth-template.json (auto-detected if not specified)",
    ),
    output: Path = typer.Option(
        "./skene/growth-plan.md",
        "-o",
        "--output",
        help="Output path for growth plan (markdown)",
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
        help="LLM provider to use (openai, gemini, anthropic/claude, ollama, generic, skene)",
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
    activation: bool = typer.Option(
        False,
        "--activation",
        help="Generate activation-focused plan using Senior Activation Engineer perspective",
    ),
    prompt: str | None = typer.Option(
        None,
        "--prompt",
        help="Additional user prompt to influence the plan generation",
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
    Generate a growth plan using Council of Growth Engineers.

    Uses manifest and template when present (auto-detected from
    ./skene/, legacy ./skene-context/, or current dir) to generate a growth plan.
    None of these context files are required.

    Examples:

        # Generate growth plan (uses any context files found)
        uvx skene plan --api-key "your-key"
        # Or: uvx skene plan --api-key "your-key"

        # Specify context directory containing manifest and template
        uvx skene plan --context ./my-context --api-key "your-key"

        # Override context file paths
        uvx skene plan --manifest ./skene/growth-manifest.json --template ./skene/growth-template.json

        # Generate activation-focused plan
        uvx skene plan --activation --api-key "your-key"

        # Generate plan with additional user context
        uvx skene plan --prompt "Focus on enterprise customers" --api-key "your-key"
    """
    rc = resolve_cli_config(
        api_key=api_key,
        provider=provider,
        model=model,
        base_url=base_url,
        quiet=quiet,
        debug=debug,
    )

    # Validate context directory if provided
    if context:
        if not context.exists():
            error(f"Context directory does not exist: {context}")
            raise typer.Exit(1)
        if not context.is_dir():
            error(f"Context path is not a directory: {context}")
            raise typer.Exit(1)

    from skene.output_paths import bundle_dir_candidates

    # Auto-detect manifest (growth-manifest.json is the standard name from analyze)
    if manifest is None:
        default_paths: list[Path] = []
        if context:
            default_paths.append(context / "growth-manifest.json")
        default_paths.extend(d / "growth-manifest.json" for d in bundle_dir_candidates(Path(".")))
        default_paths.append(Path("./growth-manifest.json"))
        for p in default_paths:
            if p.exists():
                manifest = p
                break

    # Auto-detect template
    if template is None:
        default_template_paths: list[Path] = []
        if context:
            default_template_paths.append(context / "growth-template.json")
        default_template_paths.extend(d / "growth-template.json" for d in bundle_dir_candidates(Path(".")))
        default_template_paths.append(Path("./growth-template.json"))
        for p in default_template_paths:
            if p.exists():
                template = p
                break

    # If no API key and not using local provider, show sample report
    if not rc.api_key and not rc.is_local:
        sample_path = context if context else Path(".")
        warning(
            "No API key provided. Showing sample growth plan preview.\n"
            "For full AI-powered plan generation, set --api-key, SKENE_API_KEY env var, "
            "or add to .skene.config\n"
        )
        show_sample_report(sample_path, output, exclude_folders=None)
        return

    resolved_api_key = rc.api_key
    if not resolved_api_key:
        resolved_api_key = rc.provider  # Dummy key for local server

    # Handle output path: if it's a directory, append default filename
    if output.is_absolute():
        resolved_output = output.resolve()
    else:
        resolved_output = (Path.cwd() / output).resolve()

    if resolved_output.exists() and resolved_output.is_dir():
        resolved_output = (resolved_output / "growth-plan.md").resolve()
    elif not resolved_output.suffix:
        resolved_output = (resolved_output / "growth-plan.md").resolve()

    resolved_output = resolved_output.resolve()

    from skene.output_paths import is_bundle_dir_name

    plan_type = "activation plan" if activation else "growth plan"
    base = context if context else Path(".")
    default_bundle = bundle_dir_candidates(base)[0] if not context else base
    default_manifest = default_bundle / "growth-manifest.json"
    default_template = default_bundle / "growth-template.json"
    manifest_display = str(manifest.resolve()) if manifest else f"{default_manifest.resolve()} (not found)"
    template_display = str(template.resolve()) if template else f"{default_template.resolve()} (not found)"

    def _bundle_from(ref_dir: Path) -> Path | None:
        if is_bundle_dir_name(ref_dir.name):
            return ref_dir
        for candidate in bundle_dir_candidates(ref_dir):
            if candidate.exists():
                return candidate
        return None

    # Determine context directory for growth-loops and plan-steps
    context_dir_for_loops = None
    if context:
        context_dir_for_loops = context
    elif manifest:
        context_dir_for_loops = _bundle_from(manifest.parent)
    elif resolved_output:
        context_dir_for_loops = _bundle_from(resolved_output.parent)

    # Base dir for plan-steps (same logic as run_generate_plan)
    base_dir_for_steps = context_dir_for_loops
    if base_dir_for_steps is None and manifest:
        base_dir_for_steps = _bundle_from(manifest.parent) or manifest.parent
    elif base_dir_for_steps is None and resolved_output:
        base_dir_for_steps = _bundle_from(resolved_output.parent) or resolved_output.parent
    elif base_dir_for_steps is None:
        base_dir_for_steps = Path(".")

    plan_steps_path = find_plan_steps_path(base_dir_for_steps)
    plan_steps_display = str(plan_steps_path) if plan_steps_path else None

    panel_lines = [
        f"[bold blue]Generating {plan_type}[/bold blue]",
        f"Manifest: {manifest_display}",
        f"Template: {template_display}",
        f"Output: {resolved_output}",
        f"Provider: {rc.provider}",
        f"Model: {rc.model}",
    ]
    if plan_steps_display:
        panel_lines.insert(1, f"Plan steps: {plan_steps_display}")

    console.print(Panel.fit("\n".join(panel_lines), title="skene"))

    # Run async cycle generation
    async def execute_cycle():
        memo_content, _todo_data = await run_generate_plan(
            manifest_path=manifest,
            template_path=template,
            output_path=resolved_output,
            api_key=resolved_api_key,
            provider=rc.provider,
            model=rc.model,
            activation=activation,
            context_dir=context_dir_for_loops,
            user_prompt=prompt,
            debug=rc.debug,
            base_url=rc.base_url,
            no_fallback=no_fallback,
        )

        if memo_content is None:
            raise typer.Exit(1)

        success(f"Growth plan saved to: {resolved_output}")

    asyncio.run(execute_cycle())
