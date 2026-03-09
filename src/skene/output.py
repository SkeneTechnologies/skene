"""
Centralized output module for skene.

Provides:
- A single shared Rich Console instance (stderr, to keep stdout clean for piping)
- Loguru configured for file-only logging (no stderr duplication)
- Verbosity-aware output functions: status, success, error, warning, debug
- DEBUG_DIR for LLM trace logs (used by DebugLLMClient)
"""

from pathlib import Path

from loguru import logger
from rich.console import Console

# --- Loguru: file-only logging ---
# Remove the default stderr handler to prevent on-screen duplication.
# All logger.* calls go to the log file only; console.print handles screen output.
logger.remove()
_STATE_DIR = Path("~/.local/state/skene").expanduser()
_STATE_DIR.mkdir(parents=True, exist_ok=True)

logger.add(
    _STATE_DIR / "skene.log",
    rotation="5 MB",
    retention="3 days",
    level="DEBUG",
)

# Shared debug directory — also used by DebugLLMClient for LLM traces
DEBUG_DIR = _STATE_DIR / "debug"

# --- Rich: single shared console ---
console = Console(stderr=True)  # status/progress to stderr, keep stdout clean for piping

# --- Verbosity state ---
_verbosity = 1  # 0=quiet, 1=normal, 2=debug


def set_quiet() -> None:
    global _verbosity
    _verbosity = 0


def set_debug() -> None:
    global _verbosity
    _verbosity = 2


# --- Output functions ---


def status(msg: str) -> None:
    """User-facing status/progress message. Printed (unless quiet) AND logged at INFO."""
    if _verbosity >= 1:
        console.print(msg)
    logger.opt(depth=1).info(msg)


def success(msg: str) -> None:
    """User-facing success. Printed (unless quiet) AND logged."""
    if _verbosity >= 1:
        console.print(f"[green]{msg}[/green]")
    logger.opt(depth=1).success(msg)


def error(msg: str) -> None:
    """User-facing error. Always printed. Always logged."""
    console.print(f"[red]Error:[/red] {msg}")
    logger.opt(depth=1).error(msg)


def warning(msg: str) -> None:
    """User-facing warning. Printed (unless quiet) AND logged."""
    if _verbosity >= 1:
        console.print(f"[yellow]Warning:[/yellow] {msg}")
    logger.opt(depth=1).warning(msg)


def debug(msg: str) -> None:
    """Diagnostic only. Logged to file always. Printed only in --debug mode."""
    if _verbosity >= 2:
        console.print(f"[dim]{msg}[/dim]")
    logger.opt(depth=1).debug(msg)
