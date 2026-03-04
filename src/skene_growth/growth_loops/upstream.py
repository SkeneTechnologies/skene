"""
Upstream push logic for skene deploy.

Builds deploy manifest, collects artifacts, and POSTs to upstream API.
"""

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

EDGE_FUNCTION_PATH = "functions/skene-growth-process/index.ts"


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
    """Headers for upstream API auth. Sends common variants so servers can use whichever they expect."""
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


def _collect_artifacts(
    project_root: Path,
    loops_dir: Path | None = None,
) -> list[dict[str, str]]:
    """
    Collect deploy artifacts: migrations, edge function, and growth-loops.
    Returns list of {path, content} with paths relative to project
    (migrations/..., functions/..., growth-loops/...).
    """
    artifacts: list[dict[str, str]] = []
    migrations_dir = project_root / "supabase" / "migrations"
    if migrations_dir.exists():
        for p in sorted(migrations_dir.glob("*.sql")):
            if "skene_growth" in p.name.lower():
                rel = f"migrations/{p.name}"
                artifacts.append({"path": rel, "content": p.read_text(encoding="utf-8")})
    edge_path = (
        project_root / "supabase" / "functions" / "skene-growth-process" / "index.ts"
    )
    if edge_path.exists():
        artifacts.append({"path": EDGE_FUNCTION_PATH, "content": edge_path.read_text(encoding="utf-8")})
    # Collect growth-loops folder
    resolved_loops_dir = loops_dir or project_root / "skene-context" / "growth-loops"
    if resolved_loops_dir.exists() and resolved_loops_dir.is_dir():
        for p in sorted(resolved_loops_dir.glob("*.json")):
            rel = f"growth-loops/{p.name}"
            artifacts.append({"path": rel, "content": p.read_text(encoding="utf-8")})
    return artifacts


def build_deploy_manifest(
    project_root: Path,
    workspace_slug: str,
    trigger_events: list[str],
    loops_count: int = 1,
    loops_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Build deploy manifest (metadata only, no artifact content).
    """
    artifacts = _collect_artifacts(project_root, loops_dir=loops_dir)
    artifact_entries = [
        {"path": a["path"], "checksum": f"sha256:{_sha256_checksum(a['content'])}"}
        for a in artifacts
    ]
    return {
        "version": "1.0",
        "pushed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "workspace_slug": workspace_slug,
        "artifacts": artifact_entries,
        "loops_count": loops_count,
        "trigger_events": trigger_events,
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
    Push deploy artifacts to upstream API.

    Returns dict: on success {"ok": True, **response}; on failure {"ok": False, "error": str}.
    """
    api_base = _api_base_from_upstream(upstream_url)
    workspace_slug = _workspace_slug_from_url(upstream_url)
    artifacts = _collect_artifacts(project_root, loops_dir=loops_dir)
    artifact_entries = [
        {"path": a["path"], "checksum": f"sha256:{_sha256_checksum(a['content'])}"}
        for a in artifacts
    ]
    manifest = {
        "version": "1.0",
        "pushed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "workspace_slug": workspace_slug,
        "artifacts": artifact_entries,
        "loops_count": loops_count,
        "trigger_events": trigger_events,
    }
    payload = {"manifest": manifest, "artifacts": artifacts}

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
            return {"ok": False, "error": "auth", "message": "Upstream auth failed. Run skene login or set SKENE_UPSTREAM_TOKEN."}
        if resp.status_code == 404:
            return {"ok": False, "error": "not_found", "message": "Upstream URL not found. Check the workspace URL."}
        return {"ok": False, "error": "server", "message": f"Upstream returned {resp.status_code}."}
    except httpx.ConnectError as e:
        return {"ok": False, "error": "network", "message": str(e)}
    except Exception as e:
        return {"ok": False, "error": "unknown", "message": str(e)}
