"""Tests for skene.cli.bundle_resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from skene.cli.bundle_resolution import bundle_resolution_root


def test_codebase_path_wins(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "skene").mkdir()
    assert bundle_resolution_root(codebase_path=sub) == sub.resolve()


def test_context_bundle_name_uses_parent(tmp_path: Path) -> None:
    root = tmp_path / "project"
    ctx = root / "skene-context"
    ctx.mkdir(parents=True)
    assert bundle_resolution_root(context_dir=ctx) == root.resolve()


def test_context_plain_dir_is_root(tmp_path: Path) -> None:
    d = tmp_path / "monorepo"
    d.mkdir()
    (d / "skene").mkdir()
    assert bundle_resolution_root(context_dir=d) == d.resolve()


def test_falls_back_to_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert bundle_resolution_root() == tmp_path.resolve()
