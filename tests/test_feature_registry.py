"""Tests for feature registry (growth-features.json merge and export)."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from skene_growth.feature_registry import (
    compute_loop_ids_by_feature,
    derive_feature_id,
    export_registry_to_format,
    load_feature_registry,
    load_features_for_build,
    merge_features_into_registry,
    merge_registry_and_enrich_manifest,
    write_feature_registry,
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


class TestMergeFeaturesIntoRegistry:
    def test_new_features_create_registry(self):
        new = [
            {
                "feature_name": "Team Invitations",
                "file_path": "src/invite.ts",
                "detected_intent": "Viral growth",
                "confidence_score": 0.9,
                "entry_point": "/invite",
                "growth_potential": [],
            },
        ]
        reg = merge_features_into_registry(new, None)
        assert reg["version"] == "1.0"
        assert len(reg["features"]) == 1
        f = reg["features"][0]
        assert f["feature_id"] == "team_invitations"
        assert f["feature_name"] == "Team Invitations"
        assert f["status"] == "active"
        assert "first_seen_at" in f
        assert "last_seen_at" in f

    def test_matching_updates_existing(self):
        now = datetime.now().isoformat()
        existing = {
            "version": "1.0",
            "features": [
                {
                    "feature_id": "team_invitations",
                    "feature_name": "Team Invitations",
                    "file_path": "src/invite.ts",
                    "first_seen_at": "2026-01-01T00:00:00Z",
                    "last_seen_at": "2026-01-01T00:00:00Z",
                    "status": "active",
                },
            ],
        }
        new = [
            {
                "feature_name": "Team Invitations",
                "file_path": "src/invite.ts",
                "detected_intent": "Updated intent",
                "confidence_score": 0.95,
                "entry_point": "/invite",
                "growth_potential": [],
            },
        ]
        reg = merge_features_into_registry(new, existing)
        assert len(reg["features"]) == 1
        f = reg["features"][0]
        assert f["first_seen_at"] == "2026-01-01T00:00:00Z"
        assert f["detected_intent"] == "Updated intent"
        assert f["status"] == "active"

    def test_missing_from_analysis_archived(self):
        existing = {
            "version": "1.0",
            "features": [
                {
                    "feature_id": "old_feature",
                    "feature_name": "Old Feature",
                    "file_path": "src/old.ts",
                    "status": "active",
                },
            ],
        }
        new = [
            {
                "feature_name": "New Feature",
                "file_path": "src/new.ts",
                "detected_intent": "New",
                "confidence_score": 0.8,
                "entry_point": None,
                "growth_potential": [],
            },
        ]
        reg = merge_features_into_registry(new, existing)
        assert len(reg["features"]) == 2
        by_id = {f["feature_id"]: f for f in reg["features"]}
        assert by_id["old_feature"]["status"] == "archived"
        assert by_id["new_feature"]["status"] == "active"

    def test_loop_ids_by_feature_passed_through(self):
        new = [
            {
                "feature_name": "CI/CD Gate",
                "file_path": "src/guard.py",
                "detected_intent": "Guards",
                "confidence_score": 0.9,
                "entry_point": "skene guard",
                "growth_potential": [],
            },
        ]
        loop_ids = {"ci_cd_gate": ["guard_ci_activation"]}
        reg = merge_features_into_registry(new, None, loop_ids_by_feature=loop_ids)
        f = reg["features"][0]
        assert f["loop_ids"] == ["guard_ci_activation"]


class TestComputeLoopIdsByFeature:
    def test_extracts_linked_feature_id(self):
        loops = [
            {"loop_id": "loop_a", "linked_feature_id": "feature_x", "linked_feature": "Feature X"},
            {"loop_id": "loop_b", "linked_feature_id": "feature_x", "linked_feature": "Feature X"},
        ]
        result = compute_loop_ids_by_feature(loops)
        assert result["feature_x"] == ["loop_a", "loop_b"]

    def test_derives_from_linked_feature_name_when_no_id(self):
        loops = [
            {"loop_id": "loop_a", "linked_feature": "Feature X"},
        ]
        result = compute_loop_ids_by_feature(loops)
        assert result["feature_x"] == ["loop_a"]

    def test_skips_loops_without_loop_id(self):
        loops = [{"linked_feature_id": "x"}, {"loop_id": "y", "linked_feature_id": "x"}]
        result = compute_loop_ids_by_feature(loops)
        assert result["x"] == ["y"]


class TestLoadWriteRegistry:
    def test_roundtrip(self, tmp_path):
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
        path = tmp_path / "growth-features.json"
        write_feature_registry(path, registry)
        loaded = load_feature_registry(path)
        assert loaded == registry

    def test_load_nonexistent_returns_none(self, tmp_path):
        assert load_feature_registry(tmp_path / "missing.json") is None


class TestMergeRegistryAndEnrichManifest:
    def test_merges_and_enriches_in_place(self, tmp_path):
        output_path = tmp_path / "skene-context" / "growth-manifest.json"
        output_path.parent.mkdir(parents=True)
        manifest_data = {
            "current_growth_features": [
                {
                    "feature_name": "Test Feature",
                    "file_path": "src/test.py",
                    "detected_intent": "Test",
                    "confidence_score": 0.9,
                    "entry_point": None,
                    "growth_potential": [],
                },
            ],
        }
        loops = [
            {"loop_id": "test_loop", "linked_feature_id": "test_feature", "linked_feature": "Test Feature"},
        ]
        merge_registry_and_enrich_manifest(manifest_data, loops, output_path)
        registry_path = output_path.parent / "growth-features.json"
        assert registry_path.exists()
        mf = manifest_data["current_growth_features"][0]
        assert mf["loop_ids"] == ["test_loop"]


class TestLoadFeaturesForBuild:
    def test_loads_from_registry(self, tmp_path):
        reg = {
            "version": "1.0",
            "features": [
                {"feature_id": "f1", "feature_name": "F1", "status": "active"},
            ],
        }
        (tmp_path / "growth-features.json").write_text(json.dumps(reg))
        result = load_features_for_build(tmp_path)
        assert len(result) == 1
        assert result[0]["feature_id"] == "f1"

    def test_fallback_to_manifest(self, tmp_path):
        manifest = {
            "current_growth_features": [
                {"feature_name": "F1", "file_path": "x"},
            ],
        }
        (tmp_path / "growth-manifest.json").write_text(json.dumps(manifest))
        result = load_features_for_build(tmp_path)
        assert len(result) == 1
        assert result[0]["feature_id"] == "f1"

    def test_returns_empty_when_nothing_found(self, tmp_path):
        assert load_features_for_build(tmp_path) == []


class TestExportRegistryToFormat:
    def test_json_format(self):
        registry = {"features": [{"feature_id": "x", "feature_name": "X"}]}
        out = export_registry_to_format(registry, "json")
        assert '"feature_id": "x"' in out

    def test_csv_format(self):
        registry = {
            "features": [
                {"feature_id": "x", "feature_name": "X", "file_path": "a", "status": "active", "loop_ids": [], "growth_pillars": []},
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
