"""
Upstream push logic for skene push.

Builds a single package (growth loops + telemetry.sql) and POSTs to upstream API.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


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


def _find_telemetry_migration(migrations_dir: Path) -> Path | None:
    """Find the latest telemetry migration (skene_growth_telemetry), not the schema."""
    if not migrations_dir.exists():
        return None
    matches = [p for p in migrations_dir.glob("*.sql") if "skene_growth_telemetry" in p.name.lower()]
    return max(matches, key=lambda p: p.name) if matches else None


def build_package(
    project_root: Path,
    loops_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Build a single package for upstream: growth_loops + telemetry_sql.

    Returns dict:
        growth_loops: list of {name, content} from growth-loops/*.json
        telemetry_sql: content of the telemetry migration, or None if missing
    """
    package: dict[str, Any] = {"growth_loops": [], "telemetry_sql": None}

    # Growth loops
    resolved_loops_dir = loops_dir or project_root / "skene-context" / "growth-loops"
    if resolved_loops_dir.exists() and resolved_loops_dir.is_dir():
        for p in sorted(resolved_loops_dir.glob("*.json")):
            package["growth_loops"].append({
                "name": p.name,
                "content": p.read_text(encoding="utf-8"),
            })

    # Telemetry migration only (not schema)
    migrations_dir = project_root / "supabase" / "migrations"
    telemetry_path = _find_telemetry_migration(migrations_dir)
    if telemetry_path:
        package["telemetry_sql"] = telemetry_path.read_text(encoding="utf-8")

    return package


def build_push_manifest(
    project_root: Path,
    workspace_slug: str,
    trigger_events: list[str],
    loops_count: int = 1,
    loops_dir: Path | None = None,
) -> dict[str, Any]:
    """Build push manifest with package checksum."""
    package = build_package(project_root, loops_dir=loops_dir)
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
    loops_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Push a single package (growth loops + telemetry.sql) to upstream API.

    Returns dict: on success {"ok": True, **response}; on failure {"ok": False, "error": str}.
    """
    api_base = _api_base_from_upstream(upstream_url)
    workspace_slug = _workspace_slug_from_url(upstream_url)
    package = build_package(project_root, loops_dir=loops_dir)
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
