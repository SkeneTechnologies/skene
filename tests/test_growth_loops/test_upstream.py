"""Tests for upstream push logic."""

from pathlib import Path
from unittest.mock import patch

from skene.growth_loops.upstream import (
    _api_base_from_upstream,
    _sha256_checksum,
    _workspace_slug_from_url,
    build_push_manifest,
    collect_push_files,
    push_to_upstream,
    validate_token,
)


class TestUpstreamHelpers:
    def test_api_base_from_upstream(self):
        # Default Skene Cloud hosts (any form) always resolve to the canonical API base.
        assert _api_base_from_upstream(None) == "https://www.skene.ai/api/v1"
        assert _api_base_from_upstream("") == "https://www.skene.ai/api/v1"
        assert _api_base_from_upstream("https://skene.ai/workspace/my-app") == "https://www.skene.ai/api/v1"
        assert _api_base_from_upstream("https://www.skene.ai/workspace/my-app") == "https://www.skene.ai/api/v1"
        assert _api_base_from_upstream("http://skene.ai") == "https://www.skene.ai/api/v1"
        assert _api_base_from_upstream("skene.ai/workspace/my-app") == "https://www.skene.ai/api/v1"
        # Custom upstreams derive {upstream}/api/v1.
        assert _api_base_from_upstream("https://x.com/workspace/foo/api/v1") == "https://x.com/workspace/foo/api/v1"
        assert _api_base_from_upstream("https://x.com/workspace/foo") == "https://x.com/workspace/foo/api/v1"

    def test_workspace_slug_from_url(self):
        assert _workspace_slug_from_url("https://skene.ai/workspace/my-app") == "my-app"
        assert _workspace_slug_from_url("https://x.com/workspace/acme-corp") == "acme-corp"

    def test_sha256_checksum(self):
        assert _sha256_checksum("hello") == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


def _file_by_path(files: list[dict[str, str]], suffix: str) -> dict[str, str] | None:
    return next((f for f in files if f["path"].endswith(suffix)), None)


class TestCollectPushFiles:
    def test_uploads_full_bundle_and_trigger_sql(self, tmp_path: Path):
        (tmp_path / "skene").mkdir(parents=True)
        (tmp_path / "skene" / "engine.yaml").write_text("version: 1\nsubjects: []\nfeatures: []\n")
        (tmp_path / "skene" / "growth-manifest.json").write_text('{"loops": []}\n')
        (tmp_path / "skene" / "schema.yaml").write_text("schema: {}\n")
        (tmp_path / "skene" / "user-journey.yaml").write_text("journey: {}\n")
        (tmp_path / "supabase" / "migrations").mkdir(parents=True)
        (tmp_path / "supabase" / "migrations" / "20260304151537_skene_triggers.sql").write_text("CREATE TRIGGER")

        files = collect_push_files(tmp_path)
        paths = sorted(f["path"] for f in files)
        assert paths == [
            "skene/engine.yaml",
            "skene/growth-manifest.json",
            "skene/schema.yaml",
            "skene/user-journey.yaml",
            "supabase/migrations/20260304151537_skene_triggers.sql",
        ]
        engine = _file_by_path(files, "skene/engine.yaml")
        assert engine is not None and engine["content"] == "version: 1\nsubjects: []\nfeatures: []\n"

    def test_excludes_schema_migration(self, tmp_path: Path):
        (tmp_path / "supabase" / "migrations").mkdir(parents=True)
        (tmp_path / "supabase" / "migrations" / "20260201000000_skene_growth_schema.sql").write_text("CREATE SCHEMA")
        (tmp_path / "supabase" / "migrations" / "20260304151537_skene_triggers.sql").write_text("CREATE TRIGGER")

        files = collect_push_files(tmp_path)
        contents = "\n".join(f["content"] for f in files)
        assert "CREATE SCHEMA" not in contents
        trigger = _file_by_path(files, "_skene_triggers.sql")
        assert trigger is not None and trigger["content"] == "CREATE TRIGGER"

    def test_uses_latest_trigger_migration(self, tmp_path: Path):
        (tmp_path / "supabase" / "migrations").mkdir(parents=True)
        (tmp_path / "supabase" / "migrations" / "20260218164139_skene_triggers.sql").write_text("-- older")
        (tmp_path / "supabase" / "migrations" / "20260304151537_skene_triggers.sql").write_text("-- latest")

        files = collect_push_files(tmp_path)
        trigger = _file_by_path(files, "_skene_triggers.sql")
        assert trigger is not None and trigger["content"] == "-- latest"
        assert trigger["path"].endswith("20260304151537_skene_triggers.sql")

    def test_includes_explicit_engine_path_outside_bundle(self, tmp_path: Path):
        custom_engine = tmp_path / "custom" / "engine.yaml"
        custom_engine.parent.mkdir(parents=True)
        custom_engine.write_text("version: 1\nsubjects: []\nfeatures: []\n")

        files = collect_push_files(tmp_path, engine_path=custom_engine)
        engine = _file_by_path(files, "custom/engine.yaml")
        assert engine is not None and engine["content"] == "version: 1\nsubjects: []\nfeatures: []\n"

    def test_falls_back_to_legacy_skene_context_bundle(self, tmp_path: Path):
        (tmp_path / "skene-context").mkdir(parents=True)
        (tmp_path / "skene-context" / "engine.yaml").write_text("version: 1\n")
        (tmp_path / "skene-context" / "feature-registry.json").write_text('{"features": []}\n')

        files = collect_push_files(tmp_path)
        paths = sorted(f["path"] for f in files)
        assert paths == ["skene-context/engine.yaml", "skene-context/feature-registry.json"]


class TestBuildPushManifest:
    def test_manifest_structure(self):
        files = [{"path": "skene/engine.yaml", "content": "version: 1\n"}]
        m = build_push_manifest("my-workspace", ["api_keys.insert"], files, loops_count=1)
        assert m["version"] == "1.0"
        assert m["workspace_slug"] == "my-workspace"
        assert m["trigger_events"] == ["api_keys.insert"]
        assert m["loops_count"] == 1
        assert "pushed_at" in m
        assert m["package_checksum"].startswith("sha256:")


class TestValidateToken:
    @patch("skene.growth_loops.upstream.httpx.get")
    def test_valid_token(self, mock_get):
        mock_get.return_value.status_code = 200
        assert validate_token("https://x.com/api/v1", "sk_xxx") is True

    @patch("skene.growth_loops.upstream.httpx.get")
    def test_invalid_token(self, mock_get):
        mock_get.return_value.status_code = 401
        assert validate_token("https://x.com/api/v1", "bad") is False


class TestPushToUpstream:
    @patch("skene.growth_loops.upstream.httpx.post")
    def test_push_success(self, mock_post, tmp_path: Path):
        (tmp_path / "skene").mkdir(parents=True)
        (tmp_path / "skene" / "engine.yaml").write_text("version: 1\nsubjects: []\nfeatures: []\n")
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
        payload = call_args.kwargs["json"]
        assert "manifest" in payload
        assert "files" in payload
        assert isinstance(payload["files"], list)
        assert payload["manifest"]["workspace_slug"] == "test"
        paths = [f["path"] for f in payload["files"]]
        assert "skene/engine.yaml" in paths

    @patch("skene.growth_loops.upstream.httpx.post")
    def test_push_200_noop_succeeds(self, mock_post, tmp_path: Path):
        (tmp_path / "skene").mkdir(parents=True)
        (tmp_path / "skene" / "engine.yaml").write_text("version: 1\nsubjects: []\nfeatures: []\n")
        (tmp_path / "supabase" / "migrations").mkdir(parents=True)
        (tmp_path / "supabase" / "migrations" / "20260304151537_skene_triggers.sql").write_text("CREATE TRIGGER")
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "status": "noop",
            "updated_paths": [],
            "push_id": None,
        }

        result = push_to_upstream(
            tmp_path,
            "https://skene.ai/workspace/test",
            "sk_token",
            ["api_keys.insert"],
            loops_count=1,
        )
        assert result["ok"] is True
        assert result["status"] == "noop"
        assert result["updated_paths"] == []

    @patch("skene.growth_loops.upstream.httpx.post")
    def test_push_401_returns_auth_error(self, mock_post, tmp_path: Path):
        mock_post.return_value.status_code = 401
        result = push_to_upstream(tmp_path, "https://x.com/workspace/w", "bad", [], 0)
        assert result["ok"] is False
        assert result["error"] == "auth"
