"""Tests for upstream push logic."""

from pathlib import Path
from unittest.mock import patch

from skene.growth_loops.upstream import (
    _api_base_from_upstream,
    _sha256_checksum,
    _workspace_slug_from_url,
    build_package,
    build_push_manifest,
    push_to_upstream,
    validate_token,
)


class TestUpstreamHelpers:
    def test_api_base_from_upstream(self):
        assert (
            _api_base_from_upstream("https://skene.ai/workspace/my-app") == "https://skene.ai/workspace/my-app/api/v1"
        )
        assert _api_base_from_upstream("https://x.com/workspace/foo/api/v1") == "https://x.com/workspace/foo/api/v1"

    def test_workspace_slug_from_url(self):
        assert _workspace_slug_from_url("https://skene.ai/workspace/my-app") == "my-app"
        assert _workspace_slug_from_url("https://x.com/workspace/acme-corp") == "acme-corp"

    def test_sha256_checksum(self):
        assert _sha256_checksum("hello") == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


class TestBuildPackage:
    def test_package_has_growth_loops_and_telemetry_sql(self, tmp_path: Path):
        (tmp_path / "skene-context" / "growth-loops").mkdir(parents=True)
        (tmp_path / "skene-context" / "growth-loops" / "loop1.json").write_text('{"loop_id": "loop1"}')
        (tmp_path / "supabase" / "migrations").mkdir(parents=True)
        telemetry_sql = tmp_path / "supabase" / "migrations" / "20260304151537_skene_telemetry.sql"
        telemetry_sql.write_text("CREATE TRIGGER")

        package = build_package(tmp_path)
        assert len(package["growth_loops"]) == 1
        assert package["growth_loops"][0]["name"] == "loop1.json"
        assert package["growth_loops"][0]["content"] == '{"loop_id": "loop1"}'
        assert package["telemetry_sql"] == "CREATE TRIGGER"

    def test_package_excludes_schema_migration(self, tmp_path: Path):
        (tmp_path / "supabase" / "migrations").mkdir(parents=True)
        (tmp_path / "supabase" / "migrations" / "20260201000000_skene_growth_schema.sql").write_text("CREATE SCHEMA")
        telemetry_sql = tmp_path / "supabase" / "migrations" / "20260304151537_skene_telemetry.sql"
        telemetry_sql.write_text("CREATE TRIGGER")

        package = build_package(tmp_path)
        assert "CREATE SCHEMA" not in (package["telemetry_sql"] or "")
        assert package["telemetry_sql"] == "CREATE TRIGGER"

    def test_package_uses_latest_telemetry_migration(self, tmp_path: Path):
        (tmp_path / "supabase" / "migrations").mkdir(parents=True)
        (tmp_path / "supabase" / "migrations" / "20260218164139_skene_telemetry.sql").write_text("-- older")
        (tmp_path / "supabase" / "migrations" / "20260304151537_skene_telemetry.sql").write_text("-- latest")

        package = build_package(tmp_path)
        assert package["telemetry_sql"] == "-- latest"

    def test_package_uses_explicit_loops_dir(self, tmp_path: Path):
        (tmp_path / "custom" / "growth-loops").mkdir(parents=True)
        (tmp_path / "custom" / "growth-loops" / "loop1.json").write_text('{"loop_id": "loop1"}')

        package = build_package(tmp_path, loops_dir=tmp_path / "custom" / "growth-loops")
        assert len(package["growth_loops"]) == 1
        assert package["growth_loops"][0]["name"] == "loop1.json"


class TestBuildPushManifest:
    def test_manifest_structure(self, tmp_path: Path):
        (tmp_path / "skene-context" / "growth-loops").mkdir(parents=True)
        (tmp_path / "skene-context" / "growth-loops" / "loop.json").write_text("{}")
        m = build_push_manifest(tmp_path, "my-workspace", ["api_keys.insert"], loops_count=1)
        assert m["version"] == "1.0"
        assert m["workspace_slug"] == "my-workspace"
        assert m["trigger_events"] == ["api_keys.insert"]
        assert m["loops_count"] == 1
        assert "pushed_at" in m
        assert "package_checksum" in m
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
        (tmp_path / "skene-context" / "growth-loops").mkdir(parents=True)
        (tmp_path / "skene-context" / "growth-loops" / "loop.json").write_text("{}")
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
        assert "package" in payload
        assert payload["manifest"]["workspace_slug"] == "test"
        assert "growth_loops" in payload["package"]
        assert "telemetry_sql" in payload["package"]

    @patch("skene.growth_loops.upstream.httpx.post")
    def test_push_401_returns_auth_error(self, mock_post, tmp_path: Path):
        mock_post.return_value.status_code = 401
        result = push_to_upstream(tmp_path, "https://x.com/workspace/w", "bad", [], 0)
        assert result["ok"] is False
        assert result["error"] == "auth"
