"""Analysis execution and summary utilities."""

import asyncio
import json
from pathlib import Path
from typing import Any, Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from skene_growth.llm import LLMClient

console = Console()


async def _show_progress_indicator(stop_event: asyncio.Event) -> None:
    """Show progress indicator with filled boxes every second."""
    count = 0
    while not stop_event.is_set():
        count += 1
        # Print filled box (█) every second
        console.print("[cyan]█[/cyan]", end="")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=1.0)
            break
        except asyncio.TimeoutError:
            continue
    # Print newline when done
    if count > 0:
        console.print()


def json_serializer(obj: Any) -> str:
    """JSON serializer for objects not serializable by default."""
    from datetime import datetime

    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


async def run_analysis(
    path: Path,
    output: Path,
    llm: LLMClient,
    verbose: bool,
    product_docs: Optional[bool] = False,
    exclude_folders: Optional[list[str]] = None,
):
    """Run the async analysis."""
    from skene_growth.analyzers import DocsAnalyzer, ManifestAnalyzer
    from skene_growth.codebase import CodebaseExplorer

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Initializing...", total=None)

        try:
            # Initialize components
            progress.update(task, description="Setting up codebase explorer...")
            codebase = CodebaseExplorer(path, exclude_folders=exclude_folders)

            # Load existing growth loops from output directory
            progress.update(task, description="Loading existing growth loops...")
            from skene_growth.growth_loops.storage import load_existing_growth_loops

            # Determine base directory for loading existing loops
            base_dir = output.parent if output.parent.name == "skene-context" else output.parent
            existing_loops = load_existing_growth_loops(base_dir)

            if existing_loops:
                progress.update(task, description=f"Found {len(existing_loops)} existing growth loop(s)...")

            # Create analyzer
            progress.update(task, description="Creating analyzer...")
            if product_docs:
                analyzer = DocsAnalyzer(existing_growth_loops=existing_loops)
                request_msg = "Generate documentation for this project"
            else:
                analyzer = ManifestAnalyzer(existing_growth_loops=existing_loops)
                request_msg = "Analyze this codebase for growth opportunities"

            # Define progress callback
            def on_progress(message: str, pct: float):
                progress.update(task, description=f"{message}")

            # Run analysis
            progress.update(task, description="Analyzing codebase...")
            result = await analyzer.run(
                codebase=codebase,
                llm=llm,
                request=request_msg,
                on_progress=on_progress,
            )

            if not result.success:
                console.print("[red]Analysis failed[/red]")
                if verbose and result.data:
                    console.print(json.dumps(result.data, indent=2, default=json_serializer))
                return None, None

            # Unwrap manifest data
            manifest_data = result.data.get("output", result.data) if "output" in result.data else result.data

            # Merge features into registry and enrich manifest
            progress.update(task, description="Merging feature registry...")
            from skene_growth.feature_registry import merge_registry_and_enrich_manifest

            merge_registry_and_enrich_manifest(manifest_data, existing_loops, output)

            # Write manifest (current snapshot)
            progress.update(task, description="Saving manifest...")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(manifest_data, indent=2, default=json_serializer))

            progress.update(task, description="Complete!")

            return result, manifest_data

        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            if verbose:
                import traceback

                console.print(traceback.format_exc())
            return None, None


def show_analysis_summary(data: dict, template_data: dict | None = None):
    """Display a summary of the analysis results.

    Args:
        data: Manifest data
        template_data: Growth template data (optional)
    """
    # Unwrap "output" key if present (from GenerateStep)
    if "output" in data and isinstance(data["output"], dict):
        data = data["output"]

    table = Table(title="Analysis Summary")
    table.add_column("Category", style="cyan")
    table.add_column("Details", style="white")

    if "tech_stack" in data:
        tech = data["tech_stack"]
        tech_items = [f"{k}: {v}" for k, v in tech.items() if v]
        table.add_row("Tech Stack", "\n".join(tech_items[:5]) or "Not detected")

    if "industry" in data and data["industry"]:
        industry = data["industry"]
        primary = industry.get("primary") or "Unknown"
        secondary = industry.get("secondary", [])
        confidence = industry.get("confidence")
        industry_str = primary
        if secondary:
            industry_str += f" ({', '.join(secondary[:3])})"
        if confidence is not None:
            industry_str += f" — {int(confidence * 100)}% confidence"
        table.add_row("Industry", industry_str)

    features = data.get("current_growth_features")
    if features:
        table.add_row("Current Growth Features", f"{len(features)} features detected")

    opportunities = data.get("growth_opportunities")
    if opportunities:
        table.add_row("Growth Opportunities", f"{len(opportunities)} opportunities identified")

    if "revenue_leakage" in data:
        leakage = data["revenue_leakage"]
        high_impact = sum(1 for item in leakage if item.get("impact") == "high")
        table.add_row(
            "Revenue Leakage",
            f"{len(leakage)} issues found ({high_impact} high impact)" if leakage else "None detected",
        )
    # Add growth template summary
    if template_data:
        if "lifecycles" in template_data:
            # New format with lifecycles
            lifecycle_count = len(template_data["lifecycles"])
            lifecycle_names = [lc["name"] for lc in template_data["lifecycles"][:3]]
            lifecycle_summary = ", ".join(lifecycle_names)
            if lifecycle_count > 3:
                lifecycle_summary += f", +{lifecycle_count - 3} more"
            table.add_row("Lifecycle Stages", f"{lifecycle_count} stages: {lifecycle_summary}")
        elif "visuals" in template_data and "lifecycleVisuals" in template_data["visuals"]:
            # Legacy format with visuals
            lifecycle_count = len(template_data["visuals"]["lifecycleVisuals"])
            lifecycle_names = list(template_data["visuals"]["lifecycleVisuals"].keys())[:3]
            lifecycle_summary = ", ".join(lifecycle_names)
            if lifecycle_count > 3:
                lifecycle_summary += f", +{lifecycle_count - 3} more"
            table.add_row("Lifecycle Stages", f"{lifecycle_count} stages: {lifecycle_summary}")

    console.print(table)


async def generate_todo_list(
    llm,
    memo_content: str,
    manifest_data: dict[str, Any],
    template_data: dict[str, Any] | None = None,
) -> tuple[str | None, list[dict[str, str]] | None]:
    """Generate an implementation todo list using the structured plan context.

    Extracts the Technical Execution section from the memo and combines it
    with the project manifest (tech stack, features) to produce specific,
    actionable engineering tasks.

    Args:
        llm: LLM client for generation
        memo_content: Full memo markdown content
        manifest_data: Project manifest with tech_stack, features, etc.
        template_data: Growth template data (optional)

    Returns:
        Tuple of (summary, todo_list) where summary is a brief description of what
        the tasks accomplish, and todo_list is a list of items with 'task' and
        'priority' keys. Returns (None, None) on failure.
    """
    import re as _re

    from skene_growth.cli.prompt_builder import extract_technical_execution

    # Extract structured Technical Execution section from the memo
    tech_exec = extract_technical_execution(memo_content)

    # Build a compact tech-stack summary the LLM can reference
    tech_stack_lines = []
    tech = manifest_data.get("tech_stack", {})
    for key, value in tech.items():
        if value:
            tech_stack_lines.append(f"- {key}: {value}")
    tech_stack_str = "\n".join(tech_stack_lines) if tech_stack_lines else "Not detected"

    project_name = manifest_data.get("project_name", "Project")

    # Build the Technical Execution context block
    if tech_exec:
        tech_exec_block = ""
        if tech_exec.get("next_build"):
            tech_exec_block += f"**The Next Build:**\n{tech_exec['next_build']}\n\n"
        if tech_exec.get("exact_logic"):
            tech_exec_block += f"**Exact Logic:**\n{tech_exec['exact_logic']}\n\n"
        if tech_exec.get("data_triggers"):
            tech_exec_block += f"**Data Triggers:**\n{tech_exec['data_triggers']}\n\n"
        if tech_exec.get("sequence"):
            tech_exec_block += f"**Sequence (Now / Next / Later):**\n{tech_exec['sequence']}\n\n"
        if tech_exec.get("confidence"):
            tech_exec_block += f"**Confidence:** {tech_exec['confidence']}\n"
    else:
        # Fallback: use a truncated memo when extraction fails
        tech_exec_block = memo_content[:3000] if len(memo_content) > 3000 else memo_content

    prompt = f"""You are a senior engineer creating an implementation todo list for the project "{project_name}".

## Tech Stack
{tech_stack_str}

## Technical Execution Plan
{tech_exec_block}

Based on the Technical Execution plan above, produce:
1. A brief summary (1-2 sentences) explaining what these implementation tasks accomplish
2. A focused, ordered todo list of engineering tasks to implement this

Rules for tasks:
- Each task must be a concrete engineering action (e.g. "Create middleware X in src/...",
  "Add event Y to analytics service").
- Reference the actual tech stack (framework, language, tools) in the tasks.
- Focus on the "Now" items from the Sequence — things to build first.
- Order tasks by implementation dependency: foundational work first, integration last.
- Do NOT include meetings, research, or vague items like "plan the architecture".
- Maximum 8 tasks.

Return ONLY a valid JSON object:
{{
  "summary": "Brief 1-2 sentence summary of what these tasks accomplish",
  "todos": [
    {{"task": "...", "priority": "high"}},
    {{"task": "...", "priority": "medium"}}
  ]
}}

priority is "high", "medium", or "low". Return only the JSON object, nothing else."""

    try:
        response = await llm.generate_content(prompt)

        # Extract the first JSON object from the response
        json_match = _re.search(r"\{[\s\S]*\}", response)
        if json_match:
            try:
                result = json.loads(json_match.group(0))
                if isinstance(result, dict):
                    summary = result.get("summary", "").strip()
                    todo_items = result.get("todos", [])

                    if isinstance(todo_items, list):
                        validated = [
                            {
                                "task": str(item["task"]).strip(),
                                "priority": item.get("priority", "medium").lower(),
                            }
                            for item in todo_items
                            if isinstance(item, dict) and "task" in item
                        ]
                        if validated:
                            return (summary if summary else None, validated)
            except json.JSONDecodeError:
                pass

        return (None, None)

    except Exception:
        return (None, None)


async def run_cycle(
    manifest_path: Path | None,
    template_path: Path | None,
    output_path: Path,
    api_key: str,
    provider: str,
    model: str,
    verbose: bool,
    activation: bool = False,
    context_dir: Path | None = None,
    user_prompt: str | None = None,
    debug: bool = False,
):
    """Run cycle generation using Council of Growth Engineers."""
    from pydantic import SecretStr

    from skene_growth.llm import create_llm_client

    todo_list = None
    memo_content = None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Initializing...", total=None)

        try:
            # Load manifest (use empty dict if missing)
            progress.update(task, description="Loading manifest...")
            if manifest_path and manifest_path.exists():
                manifest_data = json.loads(manifest_path.read_text())
            else:
                manifest_data = {"project_name": "Project", "description": "No manifest provided."}

            # Load template (use empty dict if missing)
            progress.update(task, description="Loading template...")
            if template_path and template_path.exists():
                template_data = json.loads(template_path.read_text())
            else:
                template_data = {"lifecycles": []}

            # Load growth-loops from skene-context/growth-loops folder
            progress.update(task, description="Loading growth-loops...")
            from skene_growth.growth_loops.storage import load_existing_growth_loops

            # Determine base directory for loading growth-loops
            # Use context_dir if provided, otherwise infer from output_path or manifest_path
            if context_dir:
                base_dir = context_dir
            elif manifest_path:
                # If manifest is in skene-context, use that parent
                if manifest_path.parent.name == "skene-context":
                    base_dir = manifest_path.parent
                else:
                    # Check if skene-context exists in same directory as manifest
                    potential_context = manifest_path.parent / "skene-context"
                    base_dir = potential_context if potential_context.exists() else manifest_path.parent
            elif output_path:
                # If output is in skene-context, use that parent
                if output_path.parent.name == "skene-context":
                    base_dir = output_path.parent
                else:
                    # Check if skene-context exists in same directory as output
                    potential_context = output_path.parent / "skene-context"
                    base_dir = potential_context if potential_context.exists() else output_path.parent
            else:
                # Fallback to current directory
                base_dir = Path(".")

            growth_loops = load_existing_growth_loops(base_dir)
            if growth_loops:
                progress.update(task, description=f"Found {len(growth_loops)} active growth loop(s)...")

            # Connect to LLM
            progress.update(task, description="Connecting to LLM provider...")
            llm = create_llm_client(provider, SecretStr(api_key), model, debug=debug)

            # Generate memo
            memo_type = "activation memo" if activation else "Council memo"
            progress.update(task, description=f"Generating {memo_type}...")
            from skene_growth.planner import Planner

            planner = Planner()

            # Start progress indicator for generation
            stop_event = asyncio.Event()
            progress_task = None

            try:
                progress_task = asyncio.create_task(_show_progress_indicator(stop_event))

                if activation:
                    memo_content = await planner.generate_activation_memo(
                        llm=llm,
                        manifest_data=manifest_data,
                        template_data=template_data,
                        growth_loops=growth_loops,
                        user_prompt=user_prompt,
                    )
                else:
                    memo_content = await planner.generate_council_memo(
                        llm=llm,
                        manifest_data=manifest_data,
                        template_data=template_data,
                        growth_loops=growth_loops,
                        user_prompt=user_prompt,
                    )
            finally:
                # Stop progress indicator
                if progress_task is not None:
                    stop_event.set()
                    try:
                        await progress_task
                    except Exception:
                        pass

            # Write output
            progress.update(task, description="Writing output...")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(memo_content)

            progress.update(task, description="Complete!")

            # Generate todo list from memo + structured project context
            progress.update(task, description="Generating todo list...")
            todo_summary, todo_list = await generate_todo_list(llm, memo_content, manifest_data, template_data)

            # Extract executive summary and next action from memo
            from skene_growth.cli.prompt_builder import (
                extract_executive_summary,
                extract_next_action,
            )

            executive_summary = extract_executive_summary(memo_content)
            todo_summary = extract_next_action(memo_content)

            return memo_content, (executive_summary, todo_summary, todo_list)

        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            if verbose:
                import traceback

                console.print(traceback.format_exc())
            return None, None
