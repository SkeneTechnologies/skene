"""Promote growth opportunities into concrete engine.yaml features."""

import asyncio
from pathlib import Path

import typer
from pydantic import SecretStr
from rich.panel import Panel

from skene.analyzers.plan_engine import DEFAULT_FEATURE_COUNT, plan_engine_from_manifest
from skene.cli.app import app, resolve_cli_config
from skene.output import console, error, success, warning


@app.command(name="analyse-plan")
def analyse_plan_cmd(
    path: Path | None = typer.Argument(
        None,
        help="Path to codebase / project root (omit for current directory)",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    manifest: Path = typer.Option(
        Path("./skene/growth-manifest.json"),
        "-M",
        "--manifest",
        help="Path to growth-manifest.json (run 'analyse-growth-from-schema' first)",
    ),
    schema: Path = typer.Option(
        Path("./skene/schema.yaml"),
        "-s",
        "--schema",
        help="Path to schema.yaml (run 'analyse-journey' first to generate it)",
    ),
    output: Path = typer.Option(
        Path("./skene/engine.yaml"),
        "-o",
        "--output",
        help="Output path for engine.yaml (merged with existing content by key)",
    ),
    count: int = typer.Option(
        DEFAULT_FEATURE_COUNT,
        "--count",
        "-n",
        min=1,
        max=10,
        help="Number of growth features to promote from the manifest",
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
):
    """
    Promote growth opportunities from the manifest into concrete engine.yaml features.

    Reads the schema-driven growth manifest produced by
    ``analyse-growth-from-schema`` plus the introspected ``schema.yaml``, then
    asks the LLM to turn the top ``--count`` (default 3) growth opportunities
    into fully-specified features — ``source``, ``subject_state_analysis`` and
    an optional ``action`` — and merges them into ``skene/engine.yaml`` by key.
    The same run writes ``new-features.yaml`` beside the engine file: a JSON
    array of only the features planned in that invocation.

    Examples:

        skene analyse-plan

        skene analyse-plan ./my-project -n 3

        skene analyse-plan --manifest ./skene/growth-manifest.json --schema ./skene/schema.yaml
    """
    base_path = (path if path is not None else Path(".")).resolve()
    if not base_path.exists():
        error(f"Path does not exist: {base_path}")
        raise typer.Exit(1)
    if not base_path.is_dir():
        error(f"Path is not a directory: {base_path}")
        raise typer.Exit(1)

    def _resolve(p: Path) -> Path:
        return p if p.is_absolute() else (Path.cwd() / p).resolve()

    resolved_manifest = _resolve(manifest)
    if not resolved_manifest.exists():
        error(
            f"Growth manifest not found: {resolved_manifest}\n"
            "Run 'skene analyse-growth-from-schema' first, or pass --manifest <path>."
        )
        raise typer.Exit(1)

    resolved_schema = _resolve(schema)
    if not resolved_schema.exists():
        error(
            f"Schema file not found: {resolved_schema}\n"
            "Run 'skene analyse-journey' first, or pass --schema <path>."
        )
        raise typer.Exit(1)

    resolved_output = _resolve(output)
    if resolved_output.exists() and resolved_output.is_dir():
        resolved_output = (resolved_output / "engine.yaml").resolve()
    elif not resolved_output.suffix:
        resolved_output = (resolved_output / "engine.yaml").resolve()

    rc = resolve_cli_config(
        api_key=api_key,
        provider=provider,
        model=model,
        base_url=base_url,
        quiet=quiet,
        debug=debug,
    )

    if not rc.api_key and not rc.is_local:
        error(
            "An API key is required for analyse-plan. "
            "Set --api-key, SKENE_API_KEY env var, or add api_key to .skene.config."
        )
        raise typer.Exit(1)

    resolved_api_key = rc.api_key or rc.provider

    console.print(
        Panel.fit(
            "[bold blue]Planning engine.yaml features from growth manifest[/bold blue]\n"
            f"Path: {base_path}\n"
            f"Manifest: {resolved_manifest}\n"
            f"Schema: {resolved_schema}\n"
            f"Provider: {rc.provider}\n"
            f"Model: {rc.model}\n"
            f"Features to plan: {count}\n"
            f"Output: {resolved_output}",
            title="skene · analyse-plan",
        )
    )

    from skene.llm import create_llm_client

    async def execute():
        llm = create_llm_client(
            rc.provider,
            SecretStr(resolved_api_key),
            rc.model,
            base_url=rc.base_url,
            debug=rc.debug,
            no_fallback=no_fallback,
        )

        state = await plan_engine_from_manifest(
            manifest_path=resolved_manifest,
            schema_path=resolved_schema,
            llm=llm,
            engine_path=resolved_output,
            project_root=base_path,
            feature_count=count,
        )

        if not state.selected_opportunities:
            warning("No growth opportunities were available in the manifest.")
            return

        added = len(state.delta.features) if state.delta else 0
        total = len(state.merged.features) if state.merged else 0
        sidecar = resolved_output.parent / "new-features.yaml"
        if added == 0:
            warning("No new features were produced; engine.yaml left unchanged.")
        success(
            f"engine.yaml saved to: {resolved_output} "
            f"({added} feature(s) planned, {total} total after merge)"
        )
        if state.delta is not None:
            success(f"Latest plan snapshot: {sidecar}")

    asyncio.run(execute())
