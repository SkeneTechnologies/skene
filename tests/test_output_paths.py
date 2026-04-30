"""Tests for output_paths module and Config.output_dir sticky-legacy behavior."""

from __future__ import annotations

from pathlib import Path

from skene.config import Config
from skene.output_paths import (
    BUNDLE_DIR_NAMES,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_OUTPUT_DIR_NAME,
    LEGACY_OUTPUT_DIR_NAME,
    resolve_bundle_dir,
)


def test_default_output_dir_is_skene_context():
    assert DEFAULT_OUTPUT_DIR == "./skene-context"
    assert DEFAULT_OUTPUT_DIR_NAME == "skene-context"
    assert LEGACY_OUTPUT_DIR_NAME == "skene"


def test_bundle_dir_names_prefers_new_over_legacy():
    assert BUNDLE_DIR_NAMES == ("skene-context", "skene")


def test_resolve_bundle_dir_prefers_new_when_both_exist(tmp_path: Path):
    (tmp_path / "skene").mkdir()
    (tmp_path / "skene-context").mkdir()
    resolved = resolve_bundle_dir(tmp_path)
    assert resolved == tmp_path / "skene-context"


def test_resolve_bundle_dir_finds_legacy_when_only_legacy(tmp_path: Path):
    (tmp_path / "skene").mkdir()
    resolved = resolve_bundle_dir(tmp_path)
    assert resolved == tmp_path / "skene"


def test_resolve_bundle_dir_returns_none_when_neither_exists(tmp_path: Path):
    assert resolve_bundle_dir(tmp_path) is None


class TestConfigOutputDirStickyLegacy:
    def test_explicit_value_wins(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "skene").mkdir()
        cfg = Config()
        cfg.set("output_dir", "./explicit")
        assert cfg.output_dir == "./explicit"

    def test_sticky_legacy_when_only_legacy_bundle_exists(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "skene").mkdir()
        cfg = Config()
        assert cfg.output_dir == "./skene"

    def test_default_when_no_bundle_exists(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = Config()
        assert cfg.output_dir == DEFAULT_OUTPUT_DIR

    def test_prefers_new_when_both_bundles_exist(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "skene").mkdir()
        (tmp_path / "skene-context").mkdir()
        cfg = Config()
        assert cfg.output_dir == "./skene-context"

    def test_sticky_uses_bundle_root_not_cwd(self, tmp_path, monkeypatch):
        """When CWD and target project differ, set_bundle_resolution_root picks the target layout."""
        outer = tmp_path / "other_cwd"
        outer.mkdir()
        target = tmp_path / "repo"
        target.mkdir()
        (target / "skene").mkdir()
        monkeypatch.chdir(outer)
        cfg = Config()
        cfg.set_bundle_resolution_root(target)
        assert cfg.output_dir == "./skene"
