"""Shared constants and helpers for Skene's output bundle directory.

The primary bundle directory is ``./skene/``; ``./skene-context/`` is the
legacy default and is still recognised when auto-discovering inputs so that
existing projects continue to work.
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_OUTPUT_DIR = "./skene"
LEGACY_OUTPUT_DIR_NAME = "skene-context"
DEFAULT_OUTPUT_DIR_NAME = "skene"

BUNDLE_DIR_NAMES: tuple[str, ...] = (DEFAULT_OUTPUT_DIR_NAME, LEGACY_OUTPUT_DIR_NAME)


def is_bundle_dir_name(name: str) -> bool:
    """Whether a directory name denotes a Skene bundle (new or legacy)."""
    return name in BUNDLE_DIR_NAMES


def bundle_dir_candidates(project_root: Path) -> list[Path]:
    """Candidate bundle directories, preferred first."""
    return [project_root / name for name in BUNDLE_DIR_NAMES]


def resolve_bundle_dir(project_root: Path) -> Path | None:
    """Return the first existing bundle directory under ``project_root``."""
    for candidate in bundle_dir_candidates(project_root):
        if candidate.is_dir():
            return candidate
    return None
