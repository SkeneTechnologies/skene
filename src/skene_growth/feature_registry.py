"""
Feature registry: persistent storage for growth features.

Stores features in skene-context/growth-features.json with merge-update semantics.
Features survive across analyze runs; analyze adds/updates but does not erase.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

GROWTH_PILLARS = ("onboarding", "engagement", "retention")
FEATURE_REGISTRY_FILENAME = "growth-features.json"
REGISTRY_VERSION = "1.0"


def derive_feature_id(feature_name: str) -> str:
    """
    Convert feature name to a stable snake_case identifier.

    Args:
        feature_name: Human-readable feature name

    Returns:
        Snake_case identifier matching pattern ^[a-z0-9_]+$
    """
    result = feature_name.lower()
    result = re.sub(r"[:\-\s/\\]+", "_", result)
    result = re.sub(r"[^a-z0-9_]", "", result)
    result = re.sub(r"_+", "_", result)
    result = result.strip("_")
    if not result or not re.match(r"^[a-z0-9_]+$", result):
        return "unknown_feature"
    return result


def _feature_to_registry_item(
    f: dict[str, Any],
    now: str,
    is_new: bool,
    loop_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Convert manifest feature dict to registry item format."""
    feature_id = derive_feature_id(f.get("feature_name", ""))
    return {
        "feature_name": f.get("feature_name", ""),
        "feature_id": feature_id,
        "file_path": f.get("file_path", ""),
        "detected_intent": f.get("detected_intent", ""),
        "growth_pillars": list(f.get("growth_pillars", [])),
        "loop_ids": loop_ids or list(f.get("loop_ids", [])),
        "confidence_score": float(f.get("confidence_score", 0.0)),
        "entry_point": f.get("entry_point"),
        "growth_potential": list(f.get("growth_potential", [])),
        "first_seen_at": now if is_new else f.get("first_seen_at", now),
        "last_seen_at": now,
        "status": "active",
    }


def _match_feature(
    new_f: dict[str, Any],
    existing: dict[str, Any],
) -> bool:
    """Match new feature to existing by feature_id or feature_name + file_path."""
    new_id = derive_feature_id(new_f.get("feature_name", ""))
    if new_id and new_id == existing.get("feature_id"):
        return True
    name_match = (
        new_f.get("feature_name", "").strip().lower()
        == existing.get("feature_name", "").strip().lower()
    )
    path_match = (
        new_f.get("file_path", "").strip()
        == existing.get("file_path", "").strip()
    )
    return bool(name_match and path_match)


def merge_features_into_registry(
    new_features: list[dict[str, Any]],
    existing_registry: dict[str, Any] | None,
    now: datetime | None = None,
    loop_ids_by_feature: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """
    Merge current analysis features into the registry.

    - New features are added with first_seen_at = now.
    - Matched features are updated, last_seen_at = now, status = active.
    - Registry features not in new analysis get status = archived.

    Args:
        new_features: current_growth_features from manifest analysis
        existing_registry: previously loaded registry or None
        now: timestamp for first_seen_at/last_seen_at
        loop_ids_by_feature: mapping feature_id -> list of loop_ids (from reverse link)

    Returns:
        Updated registry dict ready to write
    """
    now_str = (now or datetime.now()).isoformat()
    loop_ids_by_feature = loop_ids_by_feature or {}

    existing_list = []
    if existing_registry and "features" in existing_registry:
        existing_list = list(existing_registry["features"])
    elif existing_registry and isinstance(existing_registry.get("features"), list):
        existing_list = existing_registry["features"]

    matched_ids: set[str] = set()
    merged: list[dict[str, Any]] = []

    for new_f in new_features:
        feature_id = derive_feature_id(new_f.get("feature_name", ""))
        loop_ids = loop_ids_by_feature.get(feature_id, new_f.get("loop_ids", []))

        found = False
        for ex in existing_list:
            if _match_feature(new_f, ex):
                item = _feature_to_registry_item(new_f, now_str, is_new=False, loop_ids=loop_ids)
                item["first_seen_at"] = ex.get("first_seen_at", now_str)
                merged.append(item)
                matched_ids.add(ex.get("feature_id", ""))
                found = True
                break
        if not found:
            merged.append(
                _feature_to_registry_item(new_f, now_str, is_new=True, loop_ids=loop_ids)
            )

    for ex in existing_list:
        eid = ex.get("feature_id", "")
        if eid and eid not in matched_ids:
            archived = dict(ex)
            archived["status"] = "archived"
            merged.append(archived)

    return {
        "version": REGISTRY_VERSION,
        "updated_at": now_str,
        "features": merged,
    }


def compute_loop_ids_by_feature(loops: list[dict[str, Any]]) -> dict[str, list[str]]:
    """
    Build reverse mapping: feature_id -> list of loop_ids.

    Uses linked_feature_id from loops if present, else derives from linked_feature name.
    """
    result: dict[str, list[str]] = {}
    for loop in loops:
        loop_id = loop.get("loop_id")
        if not loop_id:
            continue
        fid = loop.get("linked_feature_id") or derive_feature_id(
            loop.get("linked_feature", "")
        )
        if fid:
            result.setdefault(fid, []).append(loop_id)
    return result


def load_feature_registry(registry_path: Path) -> dict[str, Any] | None:
    """
    Load the feature registry from disk.

    Returns None if file does not exist or is invalid.
    """
    if not registry_path.exists() or not registry_path.is_file():
        return None
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def write_feature_registry(registry_path: Path, registry: dict[str, Any]) -> Path:
    """Write the feature registry to disk."""
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return registry_path


def get_registry_path_for_output(output_path: Path) -> Path:
    """Return growth-features.json path for the given manifest output path."""
    return output_path.parent / FEATURE_REGISTRY_FILENAME


def merge_registry_and_enrich_manifest(
    manifest_data: dict[str, Any],
    existing_loops: list[dict[str, Any]],
    output_path: Path,
) -> None:
    """
    Merge current_growth_features into registry, write registry, enrich manifest in-place.

    Updates manifest_data["current_growth_features"] with loop_ids and growth_pillars
    from the merged registry.
    """
    registry_path = get_registry_path_for_output(output_path)
    existing_registry = load_feature_registry(registry_path)
    loop_ids_by_feature = compute_loop_ids_by_feature(existing_loops)
    merged_registry = merge_features_into_registry(
        manifest_data.get("current_growth_features", []),
        existing_registry,
        loop_ids_by_feature=loop_ids_by_feature,
    )
    write_feature_registry(registry_path, merged_registry)

    registry_by_id = {
        f["feature_id"]: f
        for f in merged_registry.get("features", [])
        if f.get("status") == "active"
    }
    for mf in manifest_data.get("current_growth_features", []):
        fid = mf.get("feature_id") or derive_feature_id(mf.get("feature_name", ""))
        reg = registry_by_id.get(fid)
        if reg:
            mf["loop_ids"] = reg.get("loop_ids", [])
            if not mf.get("growth_pillars") and reg.get("growth_pillars"):
                mf["growth_pillars"] = reg.get("growth_pillars", [])


def load_features_for_build(base_dir: Path) -> list[dict[str, Any]]:
    """
    Load features for build command. Registry first, manifest fallback when empty.

    Returns list of feature dicts with feature_id, feature_name, growth_pillars, etc.
    """
    registry_path = base_dir / FEATURE_REGISTRY_FILENAME
    registry = load_feature_registry(registry_path)
    if registry and registry.get("features"):
        return [f for f in registry["features"] if f.get("status") == "active"]

    manifest_path = base_dir / "growth-manifest.json"
    if manifest_path.exists():
        try:
            manifest_data = json.loads(manifest_path.read_text())
            result = []
            for f in manifest_data.get("current_growth_features", []):
                d = dict(f)
                if "feature_id" not in d:
                    d["feature_id"] = derive_feature_id(d.get("feature_name", ""))
                if "growth_pillars" not in d:
                    d["growth_pillars"] = []
                result.append(d)
            return result
        except (json.JSONDecodeError, OSError):
            pass
    return []


def export_registry_to_format(registry: dict[str, Any], fmt: str) -> str:
    """
    Format registry for export. Returns string in requested format.

    Args:
        registry: Loaded registry dict
        fmt: One of "json", "csv", "markdown"

    Returns:
        Formatted string

    Raises:
        ValueError: if fmt is unknown
    """
    features = registry.get("features", [])
    fmt_lower = fmt.lower()

    if fmt_lower == "json":
        return json.dumps(registry, indent=2, ensure_ascii=False)

    if fmt_lower == "csv":
        import csv
        import io

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            ["feature_id", "feature_name", "file_path", "status", "loop_ids", "growth_pillars"]
        )
        for f in features:
            writer.writerow([
                f.get("feature_id", ""),
                f.get("feature_name", ""),
                f.get("file_path", ""),
                f.get("status", ""),
                "|".join(f.get("loop_ids", [])),
                ",".join(f.get("growth_pillars", [])),
            ])
        return buf.getvalue()

    if fmt_lower == "markdown":
        lines = ["# Growth Features\n"]
        for f in features:
            lines.append(f"## {f.get('feature_name', 'Unknown')}\n")
            lines.append(f"- **ID:** `{f.get('feature_id', '')}`")
            lines.append(f"- **Status:** {f.get('status', '')}")
            lines.append(f"- **File:** `{f.get('file_path', '')}`")
            if f.get("loop_ids"):
                lines.append(f"- **Loops:** {', '.join(f['loop_ids'])}")
            if f.get("growth_pillars"):
                lines.append(f"- **Pillars:** {', '.join(f['growth_pillars'])}")
            lines.append("")
        return "\n".join(lines)

    raise ValueError(f"Unknown format: {fmt}")
