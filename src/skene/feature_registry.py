"""
Feature registry: persistent storage for growth features.

Stores features in ``feature-registry.json``. Populated by analysis runs;
read back for export (``skene features export``) and engine tooling.
"""

import json
import re
from pathlib import Path
from typing import Any

FEATURE_REGISTRY_FILENAME = "feature-registry.json"


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
