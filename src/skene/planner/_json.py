"""Shared JSON parsing utilities for planner modules."""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL)


def strip_json_fences(text: str) -> str:
    """Strip markdown code fences from an LLM response string."""
    text = text.strip()
    match = _FENCE_PATTERN.match(text)
    return match.group(1).strip() if match else text


def parse_json_fragment(response: str) -> dict[str, Any]:
    """Parse a JSON object from an LLM response, stripping code fences if present."""
    data = json.loads(strip_json_fences(response))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object, got {type(data)}")
    return data
