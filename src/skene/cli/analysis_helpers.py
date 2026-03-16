"""Analysis execution and summary utilities."""

import asyncio
import json
from pathlib import Path
from typing import Any, Optional

from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from skene.llm import LLMClient
from skene.output import console
from skene.output import error as output_error
from skene.output import status as output_status
from skene.output import success as output_success
from skene.output import warning as output_warning


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
    debug: bool,
    product_docs: Optional[bool] = False,
    exclude_folders: Optional[list[str]] = None,
):
    """Run the async analysis."""
    from skene.analyzers import DocsAnalyzer, ManifestAnalyzer
    from skene.codebase import CodebaseExplorer

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Initializing...", total=None)

        try:
            # Initialize components
            progress.update(task, description="Setting up codebase explorer...")
            codebase = CodebaseExplorer(path, exclude_folders=exclude_folders)

            # Load existing growth loops from output directory
            progress.update(task, description="Loading existing growth loops...")
            from skene.growth_loops.storage import load_existing_growth_loops

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
                output_error("Analysis failed")
                if debug and result.data:
                    console.print(json.dumps(result.data, indent=2, default=json_serializer))
                return None, None

            # Unwrap manifest data
            manifest_data = result.data.get("output", result.data) if "output" in result.data else result.data

            # Merge features into registry and enrich manifest
            progress.update(task, description="Merging feature registry...")
            from skene.feature_registry import merge_registry_and_enrich_manifest

            merge_registry_and_enrich_manifest(manifest_data, existing_loops, output)

            # Write manifest (current snapshot)
            progress.update(task, description="Saving manifest...")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(manifest_data, indent=2, default=json_serializer))

            progress.update(task, description="Complete!")

            return result, manifest_data

        except Exception as e:
            output_error(str(e))
            if debug:
                import traceback

                console.print(traceback.format_exc())
            return None, None


async def run_features_analysis(
    path: Path,
    output: Path,
    llm: LLMClient,
    debug: bool,
    exclude_folders: Optional[list[str]] = None,
):
    """
    Run growth features analysis only and create/update the feature registry.

    Uses GrowthFeaturesAnalyzer to detect features, then merges into
    feature-registry.json and maps growth-loops.
    """
    from skene.analyzers import GrowthFeaturesAnalyzer
    from skene.codebase import CodebaseExplorer
    from skene.feature_registry import merge_registry_and_enrich_manifest
    from skene.growth_loops.storage import load_existing_growth_loops

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Initializing...", total=None)
        try:
            progress.update(task, description="Setting up codebase explorer...")
            codebase = CodebaseExplorer(path, exclude_folders=exclude_folders)

            progress.update(task, description="Loading growth loops...")
            base_dir = output.parent if output.parent.name == "skene-context" else output.parent
            existing_loops = load_existing_growth_loops(base_dir)

            progress.update(task, description="Analyzing growth features...")
            analyzer = GrowthFeaturesAnalyzer()
            result = await analyzer.run(
                codebase=codebase,
                llm=llm,
                request="Identify growth features in this codebase",
                on_progress=lambda msg, pct: progress.update(task, description=msg),
            )

            if not result.success:
                output_error("Features analysis failed")
                if debug and result.data:
                    console.print(json.dumps(result.data, indent=2, default=json_serializer))
                return None, None

            raw = result.data.get("current_growth_features", [])
            if isinstance(raw, list):
                features = raw
            elif isinstance(raw, dict):
                features = raw.get("items", raw.get("current_growth_features", []))
            else:
                features = []
            manifest_data = {"current_growth_features": features}

            progress.update(task, description="Updating feature registry...")
            merge_registry_and_enrich_manifest(manifest_data, existing_loops, output)

            progress.update(task, description="Complete!")
            return result, manifest_data
        except Exception as e:
            output_error(str(e))
            if debug:
                import traceback

                console.print(traceback.format_exc())
            return None, None


def show_features_summary(data: dict) -> None:
    """Display a summary of feature registry analysis."""
    console.print("\n")
    features = data.get("current_growth_features", [])
    table = Table(title="Feature Registry")
    table.add_column("Features", style="cyan")
    table.add_column("Details", style="white")
    table.add_row("Detected", str(len(features)))
    if features:
        names = [f.get("feature_name", "?") for f in features[:5]]
        table.add_row("Sample", ", ".join(names) + ("..." if len(features) > 5 else ""))
    console.print(table)
    console.print("\n")


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
) -> str | None:
    """Generate an implementation todo list from the full growth plan.

    Uses the complete plan markdown (executive summary, all sections,
    and technical execution) to produce a markdown checklist of
    actionable engineering tasks.

    Args:
        llm: LLM client for generation
        memo_content: Full plan markdown content (all sections)

    Returns:
        Markdown string (checklist or bulleted list), or None on failure.
    """
    prompt = f"""You are an expert technical product manager and lead software engineer. Your task is to analyze the
provided technical implementation plan and extract a concise, strictly ordered list of actionable tasks to build
the feature.

Analyze the plan and output a to-do list following these strict guidelines:
1.  **Action-Oriented:** Start every task with a clear action verb (e.g., "Create", "Update", "Refactor",
    "Manual test").
2.  **File-Path Specific:** If a task involves writing code, you MUST include the exact file path mentioned in the
    plan (e.g., `app/path/to/file.tsx`).
3.  **High-Level but Comprehensive:** Do not list every single line of code or minor detail. Group the logic by file
    or major architectural boundary (e.g., Server Component vs. Client Component).
4.  **Summarize Core Logic:** For each file, briefly summarize its primary responsibilities, states, or conditional
    logic in a few words (e.g., "callback validation, session check, conditional rendering").
5.  **Sequential Order:** Order the tasks logically how a developer would build them (e.g., Backend/Server logic
    first, Frontend/UI second, Integration/Testing last).
6.  **Include Verification:** The final task must ALWAYS be a manual end-to-end testing step that defines the success
    criteria of the flow based on the plan.

CRITICAL CONSTRAINT — ITEM COUNT:
- Target: 5 items or fewer.
- Absolute maximum: 7 items. You MUST NOT output more than 7 items under any circumstances.
- Merge related work into a single item rather than listing separate sub-tasks.

Format the output as a simple Markdown checklist. Output ONLY the checklist, nothing else.

Here is the plan to process:
{memo_content}"""

    max_items = 7

    try:
        response = await llm.generate_content(prompt)
        text = (response or "").strip()
        if not text:
            return None

        lines = text.splitlines()
        kept: list[str] = []
        item_count = 0
        for line in lines:
            if line.strip().startswith(("-", "*")):
                item_count += 1
                if item_count > max_items:
                    break
            kept.append(line)

        return "\n".join(kept).strip() or None
    except Exception:
        return None


async def run_generate_plan(
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
    no_fallback: bool | None = False,
    base_url: str | None = None,
):
    """Run cycle generation using Council of Growth Engineers."""
    from pydantic import SecretStr

    from skene.llm import create_llm_client

    memo_content = None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
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
            from skene.growth_loops.storage import load_existing_growth_loops

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
            output_status(f"Connecting to LLM provider ({provider}/{model})")
            llm = create_llm_client(
                provider, SecretStr(api_key), model, debug=debug, base_url=base_url, no_fallback=no_fallback
            )

            # Generate memo
            memo_type = "activation memo" if activation else "growth plan"
            progress.update(task, description=f"Generating {memo_type}...")
            output_status(f"Generating {memo_type}")
            from skene.planner import DEFAULT_PLAN_STEPS, Planner, load_plan_steps

            planner = Planner()

            output_path.parent.mkdir(parents=True, exist_ok=True)

            growth_plan = None
            tokens_used: list[dict[str, int]] = []
            if activation:
                # Activation memo: single LLM call with progress spinner
                stop_event = asyncio.Event()
                progress_task = asyncio.create_task(_show_progress_indicator(stop_event))
                try:
                    memo_content = await planner.generate_activation_memo(
                        llm=llm,
                        manifest_data=manifest_data,
                        template_data=template_data,
                        growth_loops=growth_loops,
                        user_prompt=user_prompt,
                    )
                finally:
                    stop_event.set()
                    try:
                        await progress_task
                    except Exception:
                        pass
                output_path.write_text(memo_content)
            else:
                # Growth plan: multi-step orchestration with incremental writes
                # Use base_dir for plan-steps so we search the same directory as growth-loops
                from skene.planner import find_plan_steps_path
                from skene.planner.steps import PlanStepsParseError

                plan_steps_path = find_plan_steps_path(base_dir)
                if plan_steps_path:
                    output_success(f"Plan steps: {plan_steps_path}")
                    try:
                        plan_steps = await load_plan_steps(context_dir=base_dir, llm=llm)
                        output_success(f"Inferred {len(plan_steps)} custom section(s):")
                        for i, step in enumerate(plan_steps, 1):
                            output_status(f"  {i}. {step.title}")
                    except PlanStepsParseError as exc:
                        output_warning(f"Could not parse plan-steps.md: {exc}")
                        output_warning("Falling back to default sections")
                        plan_steps = DEFAULT_PLAN_STEPS
                else:
                    plan_steps = DEFAULT_PLAN_STEPS
                    output_status(f"No plan-steps.md found, using {len(plan_steps)} default section(s)")

                accumulated_chunks: list[str] = []

                def on_step(
                    step_number: int,
                    title: str,
                    markdown_chunk: str,
                    usage: dict[str, int] | None = None,
                ) -> None:
                    if usage is not None:
                        tokens_used.append(usage)
                    suffix = ""
                    if usage:
                        inp = usage.get("input_tokens", 0)
                        out = usage.get("output_tokens", 0)
                        suffix = f" ({out:,} out / {inp:,} in)"
                    output_success(f"Generated section: {title}{suffix}")
                    accumulated_chunks.append(markdown_chunk)
                    output_path.write_text("\n".join(accumulated_chunks) + "\n")

                project_name_from_file = (
                    manifest_data.get("project_name") if (manifest_path and manifest_path.exists()) else None
                )
                memo_content, growth_plan = await planner.generate_growth_plan(
                    llm=llm,
                    manifest_data=manifest_data,
                    template_data=template_data,
                    growth_loops=growth_loops,
                    user_prompt=user_prompt,
                    plan_steps=plan_steps,
                    on_step=on_step,
                    project_name_from_file=project_name_from_file,
                )
                output_path.write_text(memo_content)

            progress.update(task, description="Complete!")

            # Generate todo list from the full plan content
            progress.update(task, description="Generating todo list...")
            output_status("Generating todo list")
            todo_markdown = await generate_todo_list(llm, memo_content)

            # Append todo section to markdown
            todo_content = (todo_markdown or "").strip()
            memo_content = memo_content.rstrip() + "\n\n## Todo\n\n" + todo_content + ("\n" if todo_content else "")
            output_path.write_text(memo_content)

            # Save structured JSON alongside markdown (council memo only)
            if growth_plan is not None:
                json_path = output_path.with_suffix(".json")
                json_data = json.loads(growth_plan.model_dump_json())
                json_data["todos"] = todo_markdown.strip() if todo_markdown else ""
                json_path.write_text(json.dumps(json_data, indent=2))

            if growth_plan is not None:
                executive_summary = growth_plan.executive_summary
                todo_summary = growth_plan.sections[0].content if growth_plan.sections else None
            else:
                from skene.cli.prompt_builder import (
                    extract_executive_summary,
                    extract_next_action,
                )

                executive_summary = extract_executive_summary(memo_content)
                todo_summary = extract_next_action(memo_content)

            # Print summary (Executive Summary + dynamic sections + Technical Execution)
            middle_count = len(growth_plan.sections) if growth_plan else 0
            section_count = 1 + middle_count + 1  # Executive Summary + sections + Technical Execution
            todo_count = sum(
                1 for line in (todo_markdown or "").splitlines() if line.strip().startswith(("-", "*"))
            ) or (1 if todo_markdown else 0)
            output_success(f"Summary: {section_count} sections, {todo_count} todo items")
            total_in = sum(u.get("input_tokens", 0) for u in tokens_used)
            total_out = sum(u.get("output_tokens", 0) for u in tokens_used)
            if total_in > 0 or total_out > 0:
                output_status(f"Total tokens: {total_in:,} in / {total_out:,} out")

            return memo_content, (executive_summary, todo_summary, todo_markdown)

        except Exception as e:
            output_error(str(e))
            if verbose:
                import traceback

                console.print(traceback.format_exc())
            return None, None
