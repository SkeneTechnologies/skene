"""
Upstream push logic for skene push.

Builds a single package (engine.yaml, feature-registry.json, trigger.sql) and POSTs to upstream API.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from skene.feature_registry import registry_path_for_project
from skene.growth_loops.push import find_trigger_migration


def _api_base_from_upstream(upstream_url: str) -> str:
    """Resolve API base URL from upstream workspace URL."""
    base = upstream_url.rstrip("/")
    if not base.endswith("/api/v1"):
        base = f"{base}/api/v1"
    return base


def _workspace_slug_from_url(upstream_url: str) -> str:
    """Extract workspace slug from URL like https://skene.ai/workspace/my-app."""
    base = upstream_url.rstrip("/")
    if "/workspace/" in base:
        return base.split("/workspace/")[-1].split("/")[0] or "default"
    return "default"


def _sha256_checksum(content: str) -> str:
    """Compute SHA-256 hex digest of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _auth_headers(token: str) -> dict[str, str]:
    """Headers for upstream API auth."""
    t = (token or "").strip()
    return {
        "Authorization": f"Bearer {t}",
        "X-Skene-Token": t,
        "X-API-Key": t,
    }


def validate_token(api_base: str, token: str) -> bool:
    """
    Validate token via GET /me.
    Returns True if valid, False otherwise.
    """
    url = f"{api_base.rstrip('/')}/me"
    try:
        resp = httpx.get(
            url,
            headers=_auth_headers(token),
            timeout=10,
        )
        return resp.status_code == 200
    except Exception:
        return False


def build_package(
    project_root: Path,
    engine_path: Path | None = None,
    *,
    output_dir: str = "./skene-context",
) -> dict[str, Any]:
    """
    Build a single package for upstream: engine YAML, feature registry JSON, trigger SQL.

    Returns dict:
        engine_yaml: content of skene/engine.yaml (or provided engine_path), or None
        feature_registry_json: content of feature-registry.json, or None if missing
        trigger_sql: content of the trigger migration, or None if missing
    """
    package: dict[str, Any] = {
        "engine_yaml": None,
        "feature_registry_json": None,
        "trigger_sql": None,
    }

    resolved_engine_path = engine_path or project_root / "skene" / "engine.yaml"
    if resolved_engine_path.exists() and resolved_engine_path.is_file():
        package["engine_yaml"] = resolved_engine_path.read_text(encoding="utf-8")

    reg_path = registry_path_for_project(project_root, output_dir)
    if reg_path.is_file():
        package["feature_registry_json"] = reg_path.read_text(encoding="utf-8")

    migrations_dir = project_root / "supabase" / "migrations"
    trigger_path = find_trigger_migration(migrations_dir)
    if trigger_path:
        package["trigger_sql"] = trigger_path.read_text(encoding="utf-8")

    return package


def build_push_manifest(
    project_root: Path,
    workspace_slug: str,
    trigger_events: list[str],
    loops_count: int = 1,
    engine_path: Path | None = None,
    *,
    output_dir: str = "./skene-context",
) -> dict[str, Any]:
    """Build push manifest with package checksum."""
    package = build_package(project_root, engine_path=engine_path, output_dir=output_dir)
    package_json = json.dumps(package, sort_keys=True)
    return {
        "version": "1.0",
        "pushed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "workspace_slug": workspace_slug,
        "trigger_events": trigger_events,
        "loops_count": loops_count,
        "package_checksum": f"sha256:{_sha256_checksum(package_json)}",
    }


def push_to_upstream(
    project_root: Path,
    upstream_url: str,
    token: str,
    trigger_events: list[str],
    loops_count: int = 1,
    engine_path: Path | None = None,
    *,
    output_dir: str = "./skene-context",
) -> dict[str, Any]:
    """
    Push a single package (engine.yaml, feature-registry.json, trigger.sql) to upstream API.

    Returns dict: on success {"ok": True, **response}; on failure {"ok": False, "error": str}.
    """
    api_base = _api_base_from_upstream(upstream_url)
    workspace_slug = _workspace_slug_from_url(upstream_url)
    package = build_package(project_root, engine_path=engine_path, output_dir=output_dir)
    package_json = json.dumps(package, sort_keys=True)
    manifest = {
        "version": "1.0",
        "pushed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "workspace_slug": workspace_slug,
        "trigger_events": trigger_events,
        "loops_count": loops_count,
        "package_checksum": f"sha256:{_sha256_checksum(package_json)}",
    }
    payload = {"manifest": manifest, "package": package}

    url = f"{api_base.rstrip('/')}/deploys"
    try:
        resp = httpx.post(
            url,
            json=payload,
            headers=_auth_headers(token),
            timeout=60,
        )
        if resp.status_code == 201:
            return {"ok": True, **resp.json()}
        if resp.status_code in (401, 403):
            return {
                "ok": False,
                "error": "auth",
                "message": "Upstream auth failed. Run skene login or set SKENE_UPSTREAM_API_KEY.",
            }
        if resp.status_code == 404:
            return {"ok": False, "error": "not_found", "message": "Upstream URL not found. Check the workspace URL."}
        return {"ok": False, "error": "server", "message": f"Upstream returned {resp.status_code}."}
    except httpx.ConnectError as e:
        return {"ok": False, "error": "network", "message": str(e)}
    except Exception as e:
        return {"ok": False, "error": "unknown", "message": str(e)}
