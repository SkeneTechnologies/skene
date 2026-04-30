"""
Upstream push logic for skene push.

Collects bundle files as ``[{"path", "content"}]`` and POSTs to the upstream API.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from skene.growth_loops.push import find_trigger_migration
from skene.output import debug
from skene.output_paths import DEFAULT_OUTPUT_DIR, resolve_bundle_dir

SKENE_API_BASE = "https://www.skene.ai/api/v1"
_DEFAULT_SKENE_HOSTS = {"skene.ai", "www.skene.ai"}


def _is_default_skene_upstream(upstream_url: str | None) -> bool:
    """True when the upstream URL points at the hosted Skene Cloud (skene.ai)."""
    if not upstream_url:
        return True
    raw = upstream_url.strip()
    if not raw:
        return True
    candidate = raw if "://" in raw else f"https://{raw}"
    host = (urlparse(candidate).hostname or "").lower()
    return host in _DEFAULT_SKENE_HOSTS


def _api_base_from_upstream(upstream_url: str | None) -> str:
    """Resolve the Skene API base URL.

    For the hosted Skene Cloud (skene.ai / www.skene.ai in any form), always
    use ``SKENE_API_BASE``. For any other upstream, derive ``{upstream}/api/v1``.
    """
    if _is_default_skene_upstream(upstream_url):
        return SKENE_API_BASE
    base = (upstream_url or "").rstrip("/")
    if base.endswith("/api/v1"):
        return base
    return f"{base}/api/v1"


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


def _relative_path(path: Path, project_root: Path) -> str:
    """Return ``path`` as a POSIX-style string relative to ``project_root``."""
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return path.name


def _read_file_entry(path: Path, project_root: Path) -> dict[str, str] | None:
    """Read a file as a ``{path, content}`` push entry, skipping unreadable ones."""
    try:
        return {
            "path": _relative_path(path, project_root),
            "content": path.read_text(encoding="utf-8"),
        }
    except (OSError, UnicodeDecodeError):
        return None


def _bundle_dir_for_push(project_root: Path, output_dir: str | None) -> Path | None:
    """Directory whose files to upload.

    When ``output_dir`` is explicitly set (non-empty), honour it verbatim — even
    if the directory does not yet exist — so user config is never overridden.
    When unset, auto-discover an existing bundle (new-first, legacy fallback);
    if neither exists, return the default ``./skene-context`` under ``project_root``.
    """
    explicit = (output_dir or "").strip()
    if explicit:
        base = Path(explicit).expanduser()
        return base if base.is_absolute() else (project_root / base)

    discovered = resolve_bundle_dir(project_root)
    if discovered is not None:
        return discovered
    return project_root / Path(DEFAULT_OUTPUT_DIR)


def collect_push_files(
    project_root: Path,
    engine_path: Path | None = None,
    *,
    output_dir: str | None = None,
) -> list[dict[str, str]]:
    """Collect the artifacts to upload as ``[{"path", "content"}]`` entries.

    When ``output_dir`` is set, that directory is uploaded verbatim. When unset,
    the first existing bundle (``./skene-context/`` then ``./skene/``) is used,
    falling back to ``./skene-context/`` if neither exists. The latest Skene
    trigger migration under ``supabase/migrations/`` is always included; an
    explicit ``engine_path`` outside the bundle is included as well.
    """
    files: list[dict[str, str]] = []
    seen: set[Path] = set()

    def _add(path: Path) -> None:
        resolved = path.resolve()
        if resolved in seen or not resolved.is_file():
            return
        entry = _read_file_entry(resolved, project_root)
        if entry is not None:
            files.append(entry)
            seen.add(resolved)

    bundle_dir = _bundle_dir_for_push(project_root, output_dir)
    if bundle_dir is not None:
        for path in sorted(bundle_dir.rglob("*")):
            _add(path)

    if engine_path is not None:
        _add(engine_path)

    trigger_path = find_trigger_migration(project_root / "supabase" / "migrations")
    if trigger_path:
        _add(trigger_path)

    return files


def build_push_manifest(
    workspace_slug: str,
    trigger_events: list[str],
    files: list[dict[str, str]],
    loops_count: int = 1,
    *,
    upstream_url: str | None = None,
) -> dict[str, Any]:
    """Build push manifest with a checksum derived from the uploaded files.

    ``upstream_url`` is the user-configured upstream (or empty for the default
    Skene Cloud). The upstream API is expected to validate it.
    """
    files_json = json.dumps(files, sort_keys=True)
    return {
        "version": "1.0",
        "pushed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "upstream_url": (upstream_url or "").strip(),
        "workspace_slug": workspace_slug,
        "trigger_events": trigger_events,
        "loops_count": loops_count,
        "package_checksum": f"sha256:{_sha256_checksum(files_json)}",
    }


def push_to_upstream(
    project_root: Path,
    upstream_url: str,
    token: str,
    trigger_events: list[str],
    loops_count: int = 1,
    engine_path: Path | None = None,
    *,
    output_dir: str | None = None,
) -> dict[str, Any]:
    """
    Push bundle files to upstream API.

    Returns dict: on success {"ok": True, **response}; on failure {"ok": False, "error": str}.
    """
    api_base = _api_base_from_upstream(upstream_url)
    workspace_slug = _workspace_slug_from_url(upstream_url)
    files = collect_push_files(project_root, engine_path=engine_path, output_dir=output_dir)
    manifest = build_push_manifest(
        workspace_slug=workspace_slug,
        trigger_events=trigger_events,
        files=files,
        loops_count=loops_count,
        upstream_url=upstream_url,
    )
    payload = {"manifest": manifest, "files": files}

    url = f"{api_base.rstrip('/')}/push"
    try:
        resp = httpx.post(
            url,
            json=payload,
            headers=_auth_headers(token),
            timeout=60,
        )
        debug(f"Push API response: status={resp.status_code} url={url!r} body={resp.text!r}")
        if resp.status_code == 201:
            return {"ok": True, **resp.json()}
        # Upstream may return 200 when the package is identical to what is already
        # stored — not an error, just nothing to write.
        if resp.status_code == 200:
            try:
                data = resp.json()
            except Exception:
                return {
                    "ok": False,
                    "error": "server",
                    "message": "Upstream returned 200 with a non-JSON body.",
                }
            if isinstance(data, dict) and data.get("status") == "noop":
                return {**data, "ok": True}
            return {
                "ok": False,
                "error": "server",
                "message": (
                    f"Upstream returned 200 (expected 201 for a new deploy). Response: {data!r}"
                    if isinstance(data, dict)
                    else f"Upstream returned 200 with unexpected JSON: {data!r}"
                ),
            }
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
