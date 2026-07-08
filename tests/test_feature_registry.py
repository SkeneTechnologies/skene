"""Tests for feature registry (feature-registry.json load and export)."""

import json

import pytest

from skene.feature_registry import (
    FEATURE_REGISTRY_FILENAME,
    derive_feature_id,
    export_registry_to_format,
    load_feature_registry,
)


class TestDeriveFeatureId:
    def test_simple_name(self):
        assert derive_feature_id("Team Invitations") == "team_invitations"

    def test_with_special_chars(self):
        assert derive_feature_id("CI/CD Growth Gate") == "ci_cd_growth_gate"

    def test_empty_returns_fallback(self):
        assert derive_feature_id("") == "unknown_feature"

    def test_only_special_chars(self):
        assert derive_feature_id("---") == "unknown_feature"


class TestLoadRegistry:
    def test_load_roundtrip(self, tmp_path):
        registry = {
            "version": "1.0",
            "updated_at": "2026-02-12T00:00:00Z",
            "features": [
                {
                    "feature_id": "test",
                    "feature_name": "Test",
                    "file_path": "src/test.py",
                    "status": "active",
                },
            ],
        }
        path = tmp_path / FEATURE_REGISTRY_FILENAME
        path.write_text(json.dumps(registry), encoding="utf-8")
        loaded = load_feature_registry(path)
        assert loaded == registry

    def test_load_nonexistent_returns_none(self, tmp_path):
        assert load_feature_registry(tmp_path / "missing.json") is None


class TestExportRegistryToFormat:
    def test_json_format(self):
        registry = {"features": [{"feature_id": "x", "feature_name": "X"}]}
        out = export_registry_to_format(registry, "json")
        assert '"feature_id": "x"' in out

    def test_csv_format(self):
        registry = {
            "features": [
                {
                    "feature_id": "x",
                    "feature_name": "X",
                    "file_path": "a",
                    "status": "active",
                    "loop_ids": [],
                    "growth_pillars": [],
                },
            ],
        }
        out = export_registry_to_format(registry, "csv")
        assert "feature_id" in out
        assert "x" in out

    def test_markdown_format(self):
        registry = {"features": [{"feature_id": "x", "feature_name": "X"}]}
        out = export_registry_to_format(registry, "markdown")
        assert "# Growth Features" in out
        assert "## X" in out

    def test_unknown_format_raises(self):
        with pytest.raises(ValueError, match="Unknown format"):
            export_registry_to_format({}, "unknown")


