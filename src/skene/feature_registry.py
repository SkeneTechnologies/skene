"""
Feature registry: persistent storage for growth features.

Stores features in skene-context/feature-registry.json with merge-update semantics.
Features survive across analyze runs; analyze adds/updates but does not erase.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from skene.engine.storage import EngineDocument, default_engine_path, load_engine_document

GROWTH_PILLARS = ("onboarding", "engagement", "retention")
FEATURE_REGISTRY_FILENAME = "feature-registry.json"
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


def _feature_from_orphan_loop(loop: dict[str, Any], now_str: str) -> dict[str, Any]:
    """Build a minimal feature dict from an orphan loop (no linked feature)."""
    loop_id = loop.get("loop_id", "")
    name = loop.get("name") or loop.get("linked_feature") or loop_id
    feature_id = derive_feature_id(name) or derive_feature_id(loop_id) or "orphan_loop"
    return {
        "feature_name": name,
        "feature_id": feature_id,
        "file_path": loop.get("file_path", ""),
        "detected_intent": "",
        "growth_pillars": list(loop.get("growth_pillars", [])),
        "loop_ids": [loop_id] if loop_id else [],
        "confidence_score": 0.0,
        "entry_point": None,
        "growth_potential": [],
        "first_seen_at": now_str,
        "last_seen_at": now_str,
        "status": "active",
    }


def _feature_to_registry_item(
    f: dict[str, Any],
    now: str,
    is_new: bool,
    loop_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Convert manifest feature dict to registry item format."""
    feature_id = f.get("feature_id") or derive_feature_id(f.get("feature_name", ""))
    return {
        "feature_name": f.get("feature_name", ""),
        "feature_id": feature_id,
        "file_path": f.get("file_path", ""),
        "detected_intent": f.get("detected_intent", ""),
        "growth_pillars": list(f.get("growth_pillars", [])),
        "loop_ids": loop_ids or list(f.get("loop_ids", [])),
        "engine_feature_key": f.get("engine_feature_key"),
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
    new_engine_key = (new_f.get("engine_feature_key") or "").strip()
    existing_engine_key = (existing.get("engine_feature_key") or "").strip()
    if new_engine_key and new_engine_key == existing_engine_key:
        return True

    new_id = new_f.get("feature_id") or derive_feature_id(new_f.get("feature_name", ""))
    if new_id and new_id == existing.get("feature_id"):
        return True
    name_match = new_f.get("feature_name", "").strip().lower() == existing.get("feature_name", "").strip().lower()
    path_match = new_f.get("file_path", "").strip() == existing.get("file_path", "").strip()
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
        feature_id = new_f.get("feature_id") or derive_feature_id(new_f.get("feature_name", ""))
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
            merged.append(_feature_to_registry_item(new_f, now_str, is_new=True, loop_ids=loop_ids))

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


def _project_root_from_context(context_dir: Path) -> Path:
    """Resolve project root from a context directory."""
    if context_dir.name == "skene-context":
        return context_dir.parent
    return context_dir


def _engine_summary_rows(engine_doc: EngineDocument) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for feature in engine_doc.features:
        rows.append(
            {
                "key": feature.key,
                "name": feature.name,
                "source": feature.source,
                "linked_feature_id": derive_feature_id(feature.key),
            }
        )
    return rows


def _loop_ids_from_engine(engine_doc: EngineDocument) -> dict[str, list[str]]:
    """
    Build reverse mapping from registry feature_id to engine feature keys.

    We intentionally reuse loop_ids for compatibility in existing outputs.
    """
    mapping: dict[str, list[str]] = {}
    for feature in engine_doc.features:
        fid = derive_feature_id(feature.key)
        mapping.setdefault(fid, []).append(feature.key)
    return mapping


def upsert_registry_from_engine(
    engine_doc: EngineDocument,
    registry_path: Path,
) -> dict[str, Any]:
    """Upsert feature-registry entries from engine.yaml features."""
    existing_registry = load_feature_registry(registry_path)

    new_features: list[dict[str, Any]] = []
    for feature in engine_doc.features:
        new_features.append(
            {
                "feature_name": feature.name,
                "feature_id": derive_feature_id(feature.key),
                "file_path": "skene/engine.yaml",
                "detected_intent": feature.match_intent,
                "growth_pillars": [],
                "loop_ids": [feature.key],
                "engine_feature_key": feature.key,
                "confidence_score": 1.0,
                "entry_point": feature.source,
                "growth_potential": [feature.how_it_works] if feature.how_it_works else [],
            }
        )

    merged_registry = merge_features_into_registry(
        new_features,
        existing_registry,
        loop_ids_by_feature=_loop_ids_from_engine(engine_doc),
    )
    merged_registry["engine_features"] = _engine_summary_rows(engine_doc)
    write_feature_registry(registry_path, merged_registry)
    return merged_registry


def _infer_loop_feature_link(
    loop: dict[str, Any],
    features: list[dict[str, Any]],
) -> str | None:
    """
    Infer feature_id for a loop that lacks linked_feature_id/linked_feature.

    Tries: (1) requirements.files path match to feature file_path,
           (2) loop name similarity to feature name.
    Returns None if no confident match.
    """
    loop_id = loop.get("loop_id")
    if not loop_id:
        return None
    # Already has explicit link
    fid = loop.get("linked_feature_id") or (
        derive_feature_id(loop.get("linked_feature", "")) if loop.get("linked_feature") else None
    )
    if fid:
        return fid
    # Match by requirements.files path
    reqs = loop.get("requirements") or {}
    files = reqs.get("files") or []
    for fentry in files:
        path = (fentry.get("path") or "").strip()
        if not path:
            continue
        norm = path.replace("\\", "/")
        for feat in features:
            fp = (feat.get("file_path") or "").strip().replace("\\", "/")
            if fp and (norm == fp or norm.endswith("/" + fp) or fp.endswith("/" + norm)):
                return feat.get("feature_id") or derive_feature_id(feat.get("feature_name", ""))
    # Match by name (loop name contains feature name or vice versa)
    loop_name = (loop.get("name") or "").lower()
    loop_words = set(re.findall(r"[a-z0-9]+", loop_name))
    best: tuple[int, str] | None = None
    for feat in features:
        fname = (feat.get("feature_name") or "").lower()
        fwords = set(re.findall(r"[a-z0-9]+", fname))
        overlap = len(loop_words & fwords)
        if overlap >= 2:
            fid = feat.get("feature_id") or derive_feature_id(feat.get("feature_name", ""))
            if best is None or overlap > best[0]:
                best = (overlap, fid)
    return best[1] if best else None


def compute_loop_ids_by_feature(
    loops: list[dict[str, Any]],
    features: list[dict[str, Any]] | None = None,
) -> dict[str, list[str]]:
    """
    Build reverse mapping: feature_id -> list of loop_ids.

    Uses linked_feature_id from loops if present, else derives from linked_feature name.
    For loops without explicit link, infers from file paths or name similarity when
    features are provided.
    """
    result: dict[str, list[str]] = {}
    features = features or []
    for loop in loops:
        loop_id = loop.get("loop_id")
        if not loop_id:
            continue
        fid = None
        if loop.get("linked_feature_id"):
            fid = loop["linked_feature_id"]
        elif loop.get("linked_feature"):
            fid = derive_feature_id(loop["linked_feature"])
        if not fid or fid == "unknown_feature":
            fid = _infer_loop_feature_link(loop, features) if features else fid
        if fid and fid != "unknown_feature":
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
    """Return feature-registry.json path for the given manifest output path."""
    return output_path.parent / FEATURE_REGISTRY_FILENAME


def registry_path_for_project(project_root: Path, output_dir: str) -> Path:
    """
    Absolute path to feature-registry.json for the project's configured Skene output directory.

    Matches `build`: registry is a sibling of growth-manifest.json under that directory.
    """
    base = Path(output_dir).expanduser()
    resolved_base = base.resolve() if base.is_absolute() else (project_root / base).resolve()
    return get_registry_path_for_output(resolved_base / "growth-manifest.json")


def merge_registry_and_enrich_manifest(
    manifest_data: dict[str, Any],
    existing_engine_features: list[dict[str, Any]] | None,
    output_path: Path,
) -> None:
    """
    Merge current_growth_features into registry, write registry, enrich manifest in-place.

    Loads engine.yaml when existing_engine_features is None or empty.
    Stores `engine_features` summary and maps current features to engine feature keys.
    """
    registry_path = get_registry_path_for_output(output_path)
    context_dir = output_path.parent

    if existing_engine_features:
        engine_rows = existing_engine_features
    else:
        engine_rows = []
        try:
            project_root = _project_root_from_context(context_dir)
            engine_doc = load_engine_document(default_engine_path(project_root))
            engine_rows = _engine_summary_rows(engine_doc)
        except Exception:
            engine_rows = []

    existing_registry = load_feature_registry(registry_path)
    new_features = list(manifest_data.get("current_growth_features", []))

    loop_ids_by_feature: dict[str, list[str]] = {}
    for row in engine_rows:
        fid = row.get("linked_feature_id") or derive_feature_id(row.get("key", ""))
        key = row.get("key")
        if not fid or not key:
            continue
        loop_ids_by_feature.setdefault(fid, []).append(key)

    merged_registry = merge_features_into_registry(
        new_features,
        existing_registry,
        loop_ids_by_feature=loop_ids_by_feature,
    )
    merged_registry["engine_features"] = engine_rows

    write_feature_registry(registry_path, merged_registry)

    registry_by_id = {f["feature_id"]: f for f in merged_registry.get("features", []) if f.get("status") == "active"}
    for mf in manifest_data.get("current_growth_features", []):
        fid = mf.get("feature_id") or derive_feature_id(mf.get("feature_name", ""))
        reg = registry_by_id.get(fid)
        if reg:
            mf["loop_ids"] = reg.get("loop_ids", [])
            if reg.get("engine_feature_key"):
                mf["engine_feature_key"] = reg.get("engine_feature_key")
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
        writer.writerow(["feature_id", "feature_name", "file_path", "status", "loop_ids", "growth_pillars"])
        for f in features:
            writer.writerow(
                [
                    f.get("feature_id", ""),
                    f.get("feature_name", ""),
                    f.get("file_path", ""),
                    f.get("status", ""),
                    "|".join(f.get("loop_ids", [])),
                    ",".join(f.get("growth_pillars", [])),
                ]
            )
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
