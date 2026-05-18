"""Serialize a Journey model to YAML or JSON on disk.

Always dumps with ``by_alias=True`` so the ``from_`` field on Connector is
written as ``from`` (the schema key), and with ``mode='json'`` so datetimes
become ISO 8601 strings rather than Python objects.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from skene.analyzers.journey.models import Journey


def _to_serializable(journey: Journey) -> dict[str, Any]:
    return journey.model_dump(mode="json", by_alias=True, exclude_none=True)


def to_yaml(journey: Journey) -> str:
    return yaml.safe_dump(
        _to_serializable(journey),
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )


def to_json(journey: Journey, indent: int = 2) -> str:
    return json.dumps(_to_serializable(journey), indent=indent, ensure_ascii=False)


def write(journey: Journey, path: Path) -> None:
    """Write ``journey`` to ``path``. Format inferred from extension."""
    if path.suffix in {".yaml", ".yml"}:
        path.write_text(to_yaml(journey), encoding="utf-8")
    elif path.suffix == ".json":
        path.write_text(to_json(journey) + "\n", encoding="utf-8")
    else:
        raise ValueError(f"unsupported file type: {path.suffix} (expected .yaml, .yml, or .json)")
