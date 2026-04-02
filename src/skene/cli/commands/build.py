"""Build an AI prompt from your growth plan using LLM."""

import asyncio
from pathlib import Path

import typer
from pydantic import SecretStr
from rich.panel import Panel
from rich.prompt import Prompt

from skene.cli.app import ResolvedConfig, app, resolve_cli_config
from skene.cli.prompt_builder import (
    build_prompt_from_template,
    build_prompt_with_llm,
    extract_technical_execution,
    open_cursor_deeplink,
    run_claude,
    save_prompt_to_file,
)
from skene.output import console, error, success, warning
from skene.output import status as output_status


@app.command()
def build(
    plan: Path | None = typer.Option(
        None,
        "--plan",
        help="Path to growth plan markdown file",
    ),
    context: Path | None = typer.Option(
        None,
        "--context",
        "-c",
        help="Directory containing growth-plan.md (auto-detected if not specified)",
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        envvar="SKENE_API_KEY",
        help="API key for LLM (uses config if not provided)",
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
    target: str | None = typer.Option(
        None,
        "--target",
        "-t",
        help="Where to send the prompt (skip interactive menu). Options: cursor, claude, show, file",
    ),
    feature: str | None = typer.Option(
        None,
        "--feature",
        "-f",
        help="Bias toward this feature name when linking the loop",
    ),
    skip_migrations: bool = typer.Option(
        False,
        "--skip-migrations",
        help="Skip writing Supabase trigger migrations from engine.yaml features",
    ),
):
    """
    Build an AI prompt from your growth plan using LLM, then choose where to send it.

    Workflow:
    1. Extracts Technical Execution from growth plan
    2. Builds and merges skene/engine.yaml
    3. Updates skene-context/feature-registry.json from engine features
    4. Builds Supabase migrations from actionable engine features
    5. Asks where to send: Cursor, Claude, or Show
    6. Generates implementation prompt with LLM and executes

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
    rc = resolve_cli_config(
        api_key=api_key,
        provider=provider,
        model=model,
        base_url=base_url,
        quiet=quiet,
        debug=debug,
    )

    # Validate --target value if provided
    valid_targets = {"cursor", "claude", "show", "file"}
    if target is not None and target not in valid_targets:
        error(f"Invalid target '{target}'. Valid options: {', '.join(sorted(valid_targets))}")
        raise typer.Exit(1)

    # Run async logic
    asyncio.run(_build_async(rc, plan, context, target, no_fallback, feature, skip_migrations))


async def _build_async(
    rc: ResolvedConfig,
    plan: Path | None,
    context: Path | None,
    target: str | None = None,
    no_fallback: bool | None = False,
    bias_feature: str | None = None,
    skip_migrations: bool = False,
):
    """Async implementation of build command."""
    # Validate LLM configuration
    if not rc.api_key or not rc.provider:
        error(
            "LLM configuration required.\n\n"
            "Please set api_key and provider in one of:\n"
            "  1. .skene.config (in current directory)\n"
            "  2. ~/.config/skene/config\n"
            "  3. Command options: --api-key and --provider\n"
            "  4. Environment: SKENE_API_KEY\n\n"
            "Example config:\n"
            '  api_key = "your-api-key"\n'
            '  provider = "gemini"  # or anthropic, openai, ollama, generic, skene\n'
        )
        raise typer.Exit(1)

    # Auto-detect plan file
    if plan is None:
        default_paths = []
        if context:
            if not context.exists():
                error(f"Context directory does not exist: {context}")
                raise typer.Exit(1)
            if not context.is_dir():
                error(f"Context path is not a directory: {context}")
                raise typer.Exit(1)
            default_paths.append(context / "growth-plan.md")

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
        error(
            "Growth plan not found.\n\n"
            "Please ensure a growth plan exists at one of:\n"
            "  - ./skene-context/growth-plan.md (default)\n"
            "  - ./growth-plan.md\n"
            "  - Or specify a custom path with --plan\n\n"
            "Generate a plan first with: skene plan"
        )
        raise typer.Exit(1)

    # Extract Technical Execution section from JSON
    technical_execution = extract_technical_execution(plan)

    if not technical_execution:
        error(
            "Could not extract Technical Execution section from growth plan.\n"
            "Please ensure a growth-plan.json file exists alongside your growth-plan.md.\n"
            "Re-generate the plan with: skene plan\n"
        )
        raise typer.Exit(1)

    # Create LLM client
    try:
        from skene.llm import create_llm_client

        llm = create_llm_client(
            rc.provider,
            SecretStr(rc.api_key),
            rc.model,
            base_url=rc.base_url,
            debug=rc.debug,
            no_fallback=no_fallback,
        )
        console.print("")
        output_status(f"Using {rc.provider} ({rc.model})")
    except Exception as e:
        error(f"Failed to create LLM client: {e}")
        raise typer.Exit(1)

    # Display the technical execution context
    console.print(f"[bold blue]Technical Execution:[/bold blue] {plan}\n")
    display_text = technical_execution.get("overview") or technical_execution.get("next_build")
    if display_text:
        console.print(
            Panel(
                display_text,
                title="[bold cyan]Technical Execution[/bold cyan]",
                border_style="cyan",
                padding=(1, 2),
            )
        )

    # 2. Engine build
    try:
        from skene.engine import (
            default_engine_path,
            engine_features_to_loop_definitions,
            ensure_engine_dir,
            generate_engine_delta_with_llm,
            load_engine_document,
            merge_engine_documents,
            write_engine_document,
        )
        from skene.feature_registry import (
            get_registry_path_for_output,
            load_features_for_build,
            upsert_registry_from_engine,
        )
        from skene.growth_loops.push import build_loops_to_supabase, ensure_base_schema_migration

        # Determine base output directory
        if context and context.exists():
            base_output_dir = context
        else:
            base_output_dir = Path(rc.config.output_dir)

        project_root = Path.cwd()
        if context and context.exists() and context.resolve().name == "skene-context":
            project_root = context.resolve().parent

        ensure_engine_dir(project_root)
        engine_path = default_engine_path(project_root)
        existing_engine = load_engine_document(engine_path)

        features = load_features_for_build(base_output_dir)
        output_status("Generating engine delta")
        engine_delta = await generate_engine_delta_with_llm(
            llm=llm,
            technical_execution=technical_execution,
            plan_path=plan.resolve(),
            codebase_path=project_root,
            existing_engine=existing_engine,
            registry_features=features if features else None,
            bias_feature_name=bias_feature,
        )
        merged_engine = merge_engine_documents(existing_engine, engine_delta)
        write_engine_document(engine_path, merged_engine)
        output_status(f"Updated engine file: {engine_path}")

        registry_output_path = base_output_dir / "growth-manifest.json"
        registry_path = get_registry_path_for_output(registry_output_path)
        upsert_registry_from_engine(merged_engine, registry_path)
        output_status(f"Updated feature registry: {registry_path}")

        if not skip_migrations:
            schema_path = ensure_base_schema_migration(project_root)
            output_status(f"Schema migration: {schema_path}")

            loop_defs = engine_features_to_loop_definitions(merged_engine)
            if loop_defs:
                migration_path = build_loops_to_supabase(loop_defs, project_root)
                output_status(f"Trigger migration: {migration_path}")
            else:
                warning("No engine features with `action` were found; trigger migration was not generated.")

    except Exception as e:
        # Don't fail the whole build if storage fails
        warning(f"Failed to update engine artifacts: {e}")
        if rc.debug:
            import traceback

            console.print(traceback.format_exc())

    # 3. Ask build location (where to send the prompt)
    if target is None:
        console.print("[bold cyan]Where do you want to send the implementation prompt?[/bold cyan]")
        try:
            import questionary

            choices_list = [
                questionary.Choice("Cursor (open via deep link)", value="cursor"),
                questionary.Choice("Claude (open in terminal)", value="claude"),
                questionary.Choice("Show full prompt", value="show"),
                questionary.Choice("I build it myself", value="cancel"),
            ]
            selection = questionary.select(
                "",
                choices=choices_list,
                use_arrow_keys=True,
                use_shortcuts=True,
                instruction="(Use arrow keys to navigate, Enter to select)",
            ).ask()

            if selection == "cancel" or selection is None:
                console.print("\n[dim]Skipping prompt delivery — you'll implement this yourself.[/dim]")
                return
            target = selection
        except ImportError:
            choices = [
                "1. Cursor (open via deep link)",
                "2. Claude (open in terminal)",
                "3. Show full prompt",
                "4. I build it myself",
            ]
            for choice in choices:
                console.print(f"  {choice}")
            console.print()
            selection = Prompt.ask("Choose 1-4", choices=["1", "2", "3", "4"], default="1")
            if selection == "1":
                target = "cursor"
            elif selection == "2":
                target = "claude"
            elif selection == "3":
                target = "show"
            elif selection == "4":
                console.print("[dim]Skipping prompt delivery — you'll implement this yourself.[/dim]")
                return
            else:
                target = "cursor"

    # 4. Prompt build
    output_status("Generating implementation prompt")
    try:
        prompt = await build_prompt_with_llm(plan.resolve(), technical_execution, llm)
    except Exception as e:
        warning(f"LLM prompt generation failed: {e}")
        output_status("Falling back to template...")
        prompt = build_prompt_from_template(plan.resolve(), technical_execution)

    # Save prompt to a file for cross-platform consumption
    prompt_output_dir = plan.parent if plan else Path(rc.config.output_dir)
    prompt_file = save_prompt_to_file(prompt, prompt_output_dir)

    # Execute based on target
    if target == "file":
        success(f"Prompt saved to: {prompt_file}")

    elif target == "show":
        console.print("\n")
        console.print(Panel(prompt, title="[bold]Full Prompt[/bold]", border_style="blue", padding=(1, 2)))
        success(f"Prompt saved to: {prompt_file}")
        output_status("Copy and use as needed.")

    elif target == "cursor":
        output_status("Opening Cursor with deep link...")
        try:
            open_cursor_deeplink(prompt_file, project_root=Path.cwd())
            success("Cursor should now open with your prompt.")
            output_status(f"Prompt file: {prompt_file}")
        except RuntimeError as e:
            error(str(e))
            warning(f"Prompt saved to: {prompt_file}")
            output_status("You can open this file in Cursor manually.")
            raise typer.Exit(1)

    elif target == "claude":
        output_status("Launching Claude...")
        try:
            run_claude(prompt_file)
        except RuntimeError as e:
            error(str(e))
            warning(f"Prompt saved to: {prompt_file}")
            output_status("You can run Claude manually with the saved prompt file.")
            raise typer.Exit(1)
