"""Tests for upstream push logic."""

from pathlib import Path
from unittest.mock import patch

import pytest

from skene_growth.growth_loops.upstream import (
    _api_base_from_upstream,
    _collect_artifacts,
    _sha256_checksum,
    _workspace_slug_from_url,
    build_deploy_manifest,
    push_to_upstream,
    validate_token,
)


class TestUpstreamHelpers:
    def test_api_base_from_upstream(self):
        assert _api_base_from_upstream("https://skene.ai/workspace/my-app") == "https://skene.ai/workspace/my-app/api/v1"
        assert _api_base_from_upstream("https://x.com/workspace/foo/api/v1") == "https://x.com/workspace/foo/api/v1"

    def test_workspace_slug_from_url(self):
        assert _workspace_slug_from_url("https://skene.ai/workspace/my-app") == "my-app"
        assert _workspace_slug_from_url("https://x.com/workspace/acme-corp") == "acme-corp"

    def test_sha256_checksum(self):
        assert _sha256_checksum("hello") == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


class TestCollectArtifacts:
    def test_collects_migrations_and_edge_function(self, tmp_path: Path):
        (tmp_path / "supabase" / "migrations").mkdir(parents=True)
        (tmp_path / "supabase" / "migrations" / "20260201000000_skene_growth_schema.sql").write_text("CREATE SCHEMA")
        (tmp_path / "supabase" / "migrations" / "20260202000000_skene_growth_processor.sql").write_text("CREATE FUNCTION")
        (tmp_path / "supabase" / "migrations" / "other.sql").write_text("-- other")
        (tmp_path / "supabase" / "functions" / "skene-growth-process").mkdir(parents=True)
        (tmp_path / "supabase" / "functions" / "skene-growth-process" / "index.ts").write_text("Deno.serve")

        artifacts = _collect_artifacts(tmp_path)
        paths = [a["path"] for a in artifacts]
        assert "migrations/20260201000000_skene_growth_schema.sql" in paths
        assert "migrations/20260202000000_skene_growth_processor.sql" in paths
        assert "migrations/other.sql" not in paths
        assert "functions/skene-growth-process/index.ts" in paths

    def test_collects_growth_loops_from_context(self, tmp_path: Path):
        (tmp_path / "skene-context" / "growth-loops").mkdir(parents=True)
        (tmp_path / "skene-context" / "growth-loops" / "loop1.json").write_text('{"loop_id": "loop1"}')
        (tmp_path / "skene-context" / "growth-loops" / "loop2.json").write_text('{"loop_id": "loop2"}')

        artifacts = _collect_artifacts(tmp_path)
        paths = [a["path"] for a in artifacts]
        assert "growth-loops/loop1.json" in paths
        assert "growth-loops/loop2.json" in paths

    def test_collects_growth_loops_from_explicit_loops_dir(self, tmp_path: Path):
        (tmp_path / "custom" / "growth-loops").mkdir(parents=True)
        (tmp_path / "custom" / "growth-loops" / "loop1.json").write_text('{"loop_id": "loop1"}')

        artifacts = _collect_artifacts(tmp_path, loops_dir=tmp_path / "custom" / "growth-loops")
        paths = [a["path"] for a in artifacts]
        assert "growth-loops/loop1.json" in paths


class TestBuildDeployManifest:
    def test_manifest_structure(self, tmp_path: Path):
        (tmp_path / "supabase" / "migrations").mkdir(parents=True)
        (tmp_path / "supabase" / "migrations" / "x_skene_growth_schema.sql").write_text("CREATE SCHEMA")
        m = build_deploy_manifest(tmp_path, "my-workspace", ["api_keys.insert"], loops_count=2)
        assert m["version"] == "1.0"
        assert m["workspace_slug"] == "my-workspace"
        assert m["trigger_events"] == ["api_keys.insert"]
        assert m["loops_count"] == 2
        assert "pushed_at" in m
        assert len(m["artifacts"]) >= 1
        assert m["artifacts"][0]["path"].startswith("migrations/")
        assert "sha256:" in m["artifacts"][0]["checksum"]


class TestValidateToken:
    @patch("skene_growth.growth_loops.upstream.httpx.get")
    def test_valid_token(self, mock_get):
        mock_get.return_value.status_code = 200
        assert validate_token("https://x.com/api/v1", "sk_xxx") is True

    @patch("skene_growth.growth_loops.upstream.httpx.get")
    def test_invalid_token(self, mock_get):
        mock_get.return_value.status_code = 401
        assert validate_token("https://x.com/api/v1", "bad") is False


class TestPushToUpstream:
    @patch("skene_growth.growth_loops.upstream.httpx.post")
    def test_push_success(self, mock_post, tmp_path: Path):
        (tmp_path / "supabase" / "migrations").mkdir(parents=True)
        (tmp_path / "supabase" / "migrations" / "x_skene_growth_schema.sql").write_text("CREATE SCHEMA")
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {"commit_hash": "sha256:abc", "version": 1}

        result = push_to_upstream(
            tmp_path,
            "https://skene.ai/workspace/test",
            "sk_token",
            ["api_keys.insert"],
            loops_count=1,
        )
        assert result["ok"] is True
        assert result["commit_hash"] == "sha256:abc"
        call_args = mock_post.call_args
        assert "manifest" in call_args.kwargs["json"]
        assert "artifacts" in call_args.kwargs["json"]
        assert call_args.kwargs["json"]["manifest"]["workspace_slug"] == "test"

    @patch("skene_growth.growth_loops.upstream.httpx.post")
    def test_push_401_returns_auth_error(self, mock_post, tmp_path: Path):
        (tmp_path / "supabase" / "migrations").mkdir(parents=True)
        (tmp_path / "supabase" / "migrations" / "x.sql").write_text("--")
        mock_post.return_value.status_code = 401
        result = push_to_upstream(tmp_path, "https://x.com/workspace/w", "bad", [], 0)
        assert result["ok"] is False
        assert result["error"] == "auth"
