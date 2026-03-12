"""Decline (archive) growth plans to plans/declined with executive summary only."""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console

console = Console()


def decline_plan(context: Optional[Path], output: Path) -> Path | None:
    """
    Move current growth plan to plans/declined, preserving only the Executive Summary.

    Returns the archive path on success, or None on failure (after printing error).
    """
    if context:
        plan_path = (context / "growth-plan.md").resolve()
    else:
        plan_path = (Path.cwd() / output).resolve()
    if plan_path.exists() and plan_path.is_dir():
        plan_path = plan_path / "growth-plan.md"
    elif not plan_path.suffix:
        plan_path = plan_path / "growth-plan.md"
    if not plan_path.exists():
        console.print("[red]Error:[/red] No growth plan found to decline.")
        return None

    plans_dir = plan_path.parent / "plans" / "declined"
    plans_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = plans_dir / f"{timestamp}_plan.md"
    plan_content = plan_path.read_text()

    summary_match = re.search(
        r"(###\s+Executive\s+Summary\s*\n+.*?)(?=\n###|\n##|\Z)",
        plan_content,
        re.IGNORECASE | re.DOTALL,
    )
    archive_content = summary_match.group(1).strip() if summary_match else plan_content
    archive_path.write_text(archive_content)
    plan_path.unlink()
    return archive_path


def load_declined_plans(base_dir: Path, limit: int = 5) -> list[str]:
    """
    Load content of recent declined plans from plans/declined/.

    Args:
        base_dir: Base directory containing plans/declined/
        limit: Maximum number of recent plans to load (default: 5)

    Returns:
        List of plan contents, sorted by filename descending (newest first), limited to `limit`.
    """
    declined_dir = base_dir / "plans" / "declined"
    if not declined_dir.exists() or not declined_dir.is_dir():
        return []
    plans = []
    for p in sorted(declined_dir.glob("*_plan.md"), reverse=True)[:limit]:
        try:
            content = p.read_text()
            plans.append(content)
        except OSError as e:
            console.print(f"[yellow]Warning:[/yellow] Could not read {p.name}: {e}", style="dim")
            continue
    return plans
