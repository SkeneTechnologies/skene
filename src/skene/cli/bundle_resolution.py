"""Resolve the filesystem root used for sticky ``Config.output_dir`` (skene vs skene-context)."""

from __future__ import annotations

from pathlib import Path

from skene.output_paths import is_bundle_dir_name


def bundle_resolution_root(
    *,
    codebase_path: Path | None = None,
    context_dir: Path | None = None,
) -> Path:
    """Directory under which ``resolve_bundle_dir`` runs for sticky ``output_dir``.

    Use ``codebase_path`` when the command targets a project tree (e.g. ``skene push /repo``).
    When only ``context_dir`` is set (e.g. ``build --context ./skene-context``), use the
    parent if ``context_dir`` is a bundle folder name; otherwise use that directory.
    Falls back to :func:`pathlib.Path.cwd` when neither applies.
    """
    if codebase_path is not None:
        return codebase_path.resolve()
    if context_dir is not None:
        ctx = context_dir.resolve()
        if ctx.exists() and ctx.is_dir():
            if is_bundle_dir_name(ctx.name):
                return ctx.parent.resolve()
            return ctx
    return Path.cwd().resolve()
