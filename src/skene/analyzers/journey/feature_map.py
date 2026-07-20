"""Serialize the merged feature map to YAML on disk.

Written by ``synthesize_journey`` right after the merge step, next to
``journey.yaml``. The feature map is a first-class artifact: it is the
full evidence-backed inventory of product capabilities, independently
useful and the input the milestone synthesis is judged against.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from skene.analyzers.journey.feature import Feature


def _to_serializable(features: list[Feature], product_name: str, generated_at: datetime | None) -> dict[str, Any]:
    if generated_at is None:
        generated_at = datetime.now(timezone.utc)
    return {
        "product": {"name": product_name, "generated_at": generated_at.isoformat()},
        "features": [f.model_dump(mode="json", by_alias=False, exclude_none=True) for f in features],
    }


def features_to_yaml(features: list[Feature], product_name: str, generated_at: datetime | None = None) -> str:
    return yaml.safe_dump(
        _to_serializable(features, product_name, generated_at),
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )


def write_features(
    features: list[Feature], path: Path, product_name: str, generated_at: datetime | None = None
) -> None:
    path.write_text(features_to_yaml(features, product_name, generated_at), encoding="utf-8")
