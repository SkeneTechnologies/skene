"""Prompt building and deep link utilities for build command."""

import asyncio
import json
import os
import platform
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import quote

from rich.console import Console

console = Console()


def _load_growth_plan_json(plan_path: Path) -> dict | None:
    """Load growth-plan.json from the same directory as the plan markdown file.

    Args:
        plan_path: Path to the growth-plan.md file

    Returns:
        Parsed JSON dict or None if not found
    """
    json_path = plan_path.with_suffix(".json")
    if not json_path.exists():
        return None
    try:
        return json.loads(json_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def extract_executive_summary(plan_path: Path) -> str | None:
    """Extract the Executive Summary from the growth plan JSON.

    Args:
        plan_path: Path to the growth-plan.md file (JSON sibling is read)

    Returns:
        Executive summary text or None if not found
    """
    data = _load_growth_plan_json(plan_path)
    if data is None:
        return None
    return data.get("executive_summary") or None


def extract_next_action(plan_path: Path) -> str | None:
    """Extract 'The Next Action' section from the growth plan JSON.

    Args:
        plan_path: Path to the growth-plan.md file (JSON sibling is read)

    Returns:
        Next action content or None if not found
    """
    data = _load_growth_plan_json(plan_path)
    if data is None:
        return None
    sections = data.get("sections", [])
    if sections:
        return sections[0].get("content") or None
    return None


def extract_technical_execution(plan_path: Path) -> dict[str, str] | None:
    """Extract the Technical Execution section from the growth plan JSON.

    Args:
        plan_path: Path to the growth-plan.md file (JSON sibling is read)

    Returns:
        Dictionary with 'next_build', 'confidence', 'exact_logic',
        'data_triggers', 'stack_steps', 'sequence' or None if not found
    """
    data = _load_growth_plan_json(plan_path)
    if data is None:
        return None
    te = data.get("technical_execution")
    if te is None:
        return None
    return {
        "next_build": te.get("next_build", ""),
        "confidence": te.get("confidence", ""),
        "exact_logic": te.get("exact_logic", ""),
        "data_triggers": te.get("data_triggers", ""),
        "stack_steps": te.get("stack_steps", ""),
        "sequence": te.get("sequence", ""),
    }


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


async def build_prompt_with_llm(
    plan_path: Path,
    technical_execution: dict[str, str],
    llm,
) -> str:
    """Use LLM to build an intelligent prompt from the growth plan.

    Args:
        plan_path: Path to the growth plan file
        technical_execution: Extracted technical execution section
        llm: LLM client instance

    Returns:
        LLM-generated prompt for Cursor AI
    """
    # Prepare the context for the LLM - include all engineering content
    context_parts = []

    if technical_execution.get("next_build"):
        context_parts.append(f"What We're Building: {technical_execution['next_build']}")

    if technical_execution.get("confidence"):
        context_parts.append(f"Confidence: {technical_execution['confidence']}")

    if technical_execution.get("exact_logic"):
        context_parts.append(f"Exact Logic:\n{technical_execution['exact_logic']}")

    if technical_execution.get("data_triggers"):
        context_parts.append(f"Data Triggers:\n{technical_execution['data_triggers']}")

    if technical_execution.get("sequence"):
        context_parts.append(f"Sequence:\n{technical_execution['sequence']}")

    context = "\n\n".join(context_parts) if context_parts else "No additional context available."

    # Prompt the LLM to generate an implementation prompt
    meta_prompt = (
        f"You are a prompt engineer. Create a focused, actionable prompt "
        f"for an AI coding assistant to help implement the engineering work "
        f"described in the growth plan.\n\n"
        f"## Input Information\n\n"
        f"**Growth Plan Reference:** @{plan_path}\n\n"
        f"**Technical Execution Context:**\n"
        f"{context}\n\n"
        f"## Your Task\n\n"
        f"Generate a clear, concise prompt that:\n"
        f"1. States the engineering work to be completed based on the "
        f"Technical Execution context\n"
        f"2. Includes all relevant technical context (What We're Building, "
        f"Confidence, Logic, Data Triggers, Sequence)\n"
        f"3. References the growth plan file for additional context using "
        f"@{plan_path}\n"
        f"4. Asks for step-by-step implementation with code examples\n"
        f"5. Is direct and actionable (no fluff)\n"
        f"6. Is formatted clearly with markdown headers\n\n"
        f"Generate the prompt now (output ONLY the prompt, no explanations):"
    )

    # Start progress indicator
    stop_event = asyncio.Event()
    progress_task = None

    try:
        progress_task = asyncio.create_task(_show_progress_indicator(stop_event))
        generated_prompt = await llm.generate_content(meta_prompt)

        # Clean up any markdown code fences if present
        generated_prompt = generated_prompt.strip()
        if generated_prompt.startswith("```"):
            lines = generated_prompt.split("\n")
            generated_prompt = "\n".join(lines[1:-1]) if len(lines) > 2 else generated_prompt
        return generated_prompt
    except Exception as e:
        console.print(f"[yellow]Warning:[/yellow] LLM prompt generation failed: {e}")
        console.print("[dim]Falling back to template...[/dim]")
        return build_prompt_from_template(plan_path, technical_execution)
    finally:
        # Stop progress indicator
        if progress_task is not None:
            stop_event.set()
            try:
                await progress_task
            except Exception:
                pass


def build_prompt_from_template(plan_path: Path, technical_execution: dict[str, str]) -> str:
    """Build a prompt from static template (fallback).

    Args:
        plan_path: Path to the growth plan file
        technical_execution: Extracted technical execution section

    Returns:
        Template-generated prompt for Cursor AI
    """
    # Build technical context - include all engineering content
    context_parts = []

    if technical_execution.get("next_build"):
        context_parts.append(f"**What We're Building:** {technical_execution['next_build']}")

    if technical_execution.get("confidence"):
        context_parts.append(f"**Confidence:** {technical_execution['confidence']}")

    if technical_execution.get("exact_logic"):
        context_parts.append(f"**Exact Logic:**\n{technical_execution['exact_logic']}")

    if technical_execution.get("data_triggers"):
        context_parts.append(f"**Data Triggers:**\n{technical_execution['data_triggers']}")

    if technical_execution.get("sequence"):
        context_parts.append(f"**Sequence:**\n{technical_execution['sequence']}")

    context = "\n\n".join(context_parts) if context_parts else ""

    context_section = f"\n\n## Technical Execution Context\n\n{context}" if context else ""

    prompt = (
        f"I need to implement the engineering work described in the growth plan. "
        f"Reference @{plan_path} for full context.{context_section}\n\n"
        "Please help me implement this work. Break it down into concrete, "
        "actionable steps with code examples."
    )

    return prompt


def save_prompt_to_file(prompt: str, output_dir: Path | None = None) -> Path:
    """Save prompt content to a markdown file.

    Writes the prompt to a file in the specified directory, or to a
    system temp file if no directory is provided. This avoids shell
    escaping issues and works reliably across all platforms.

    Args:
        prompt: The prompt content to save
        output_dir: Directory to save in (creates .skene-build-prompt.md).
                    Falls back to system temp directory if not provided.

    Returns:
        Absolute path to the saved prompt file
    """
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        prompt_file = output_dir / ".skene-build-prompt.md"
        prompt_file.write_text(prompt, encoding="utf-8")
        return prompt_file.resolve()

    fd, path = tempfile.mkstemp(suffix=".md", prefix="skene-prompt-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(prompt)
    return Path(path)


def open_cursor_deeplink(prompt_file: Path, project_root: Path | None = None) -> None:
    """Open Cursor with a deep link referencing the saved prompt file.

    Creates a short deep link that points Cursor to the prompt file,
    avoiding URL length limitations from embedding the full prompt.

    Args:
        prompt_file: Path to the saved prompt markdown file
        project_root: Project root for computing relative @-references

    Raises:
        RuntimeError: If opening the deep link fails
    """
    # Build a relative path for Cursor's @-reference when possible
    if project_root:
        try:
            relative_path = prompt_file.relative_to(project_root)
            file_reference = f"@{relative_path}"
        except ValueError:
            file_reference = f"@{prompt_file}"
    else:
        file_reference = f"@{prompt_file}"

    prompt_content = prompt_file.read_text(encoding="utf-8")
    short_prompt = (
        f"The full task is saved in {file_reference}. "
        f"Read and implement the instructions in that file."
        f"\n\n{prompt_content}"
    )
    encoded_prompt = quote(short_prompt, safe="")
    deep_link = f"cursor://anysphere.cursor-deeplink/prompt?text={encoded_prompt}"

    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run(["open", deep_link], check=True)
        elif system == "Linux":
            subprocess.run(["xdg-open", deep_link], check=True)
        elif system == "Windows":
            subprocess.run(["start", deep_link], shell=True, check=True)
        else:
            raise RuntimeError(f"Unsupported platform: {system}")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to open Cursor deep link: {e}")
    except FileNotFoundError:
        raise RuntimeError(
            f"Could not find command to open URLs on {system}. "
            "Please ensure Cursor is installed and try opening the link manually."
        )


def run_claude(prompt_file: Path) -> None:
    """Run Claude CLI in the current terminal with prompt read from file.

    Reads the prompt content from the saved file and passes it directly
    to the Claude CLI process. Runs in the current terminal session -
    no new windows or platform-specific terminal launching needed.

    Works on macOS, Linux, and Windows.

    Args:
        prompt_file: Path to the saved prompt markdown file

    Raises:
        RuntimeError: If launching Claude fails
    """
    prompt_with_ref = f"The full task is saved in @{prompt_file}. Refer to that file for the complete instructions.\n\n"

    try:
        subprocess.run(["claude", prompt_with_ref], check=False)
    except FileNotFoundError:
        raise RuntimeError("Claude CLI not found. Please install it: https://docs.anthropic.com/claude-code")
    except KeyboardInterrupt:
        pass
