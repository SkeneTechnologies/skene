"""LLM generation for engine.yaml feature/subject deltas."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from skene.engine.storage import (
    EngineDocument,
    format_engine_summary,
    parse_engine_delta_response,
)
from skene.llm.base import LLMClient
from skene.output import warning
from skene.progress import run_with_progress

SCHEMA_NOT_FOUND_WARNING = "schema not found. Schema definition would significantly improve the engine building."
_SCHEMA_CANDIDATE_PATHS = (
    ("skene", "schema.yaml"),
    ("skene", "schema.md"),
    ("skene-context", "schema.yaml"),
    ("skene-context", "schema.md"),
)


def _resolve_schema_path(project_root: Path) -> Path | None:
    """Resolve schema file from skene/ or skene-context/ folders."""
    for parts in _SCHEMA_CANDIDATE_PATHS:
        candidate = project_root.joinpath(*parts)
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _load_schema_context(project_root: Path) -> tuple[str, str]:
    """
    Load schema content for engine delta prompting.

    Returns a tuple of (schema_source, schema_content).
    """
    schema_path = _resolve_schema_path(project_root)
    if schema_path is None:
        warning(SCHEMA_NOT_FOUND_WARNING)
        return ("not found", "")

    try:
        schema_content = schema_path.read_text(encoding="utf-8").strip()
    except Exception as exc:
        warning(f"Failed to read schema file at {schema_path}: {exc}")
        return (str(schema_path), "")

    return (str(schema_path), schema_content)


def _derive_feature_id(value: str) -> str:
    result = (value or "").lower()
    result = re.sub(r"[:\-\s/\\]+", "_", result)
    result = re.sub(r"[^a-z0-9_]", "", result)
    result = re.sub(r"_+", "_", result).strip("_")
    return result or "generated_feature"


def _format_registry_features_for_prompt(features: list[dict[str, Any]]) -> str:
    if not features:
        return "(No known registry features. Define new features when needed.)"

    lines = ["Known registry features:"]
    for item in features:
        fid = item.get("feature_id", "")
        name = item.get("feature_name", "?")
        entry = item.get("entry_point") or item.get("file_path") or ""
        lines.append(f"- {name} (id: {fid}) {entry}".strip())
    return "\n".join(lines)


def _fallback_engine_delta(
    technical_execution: dict[str, str],
    bias_feature_name: str | None = None,
) -> EngineDocument:
    label = (
        bias_feature_name
        or technical_execution.get("overview")
        or technical_execution.get("next_build")
        or "Generated Feature"
    )
    first_line = next((line.strip() for line in label.splitlines() if line.strip()), "Generated Feature")
    key = _derive_feature_id(first_line)

    return EngineDocument.model_validate(
        {
            "version": 1,
            "subjects": [
                {
                    "key": "user",
                    "table": "auth.users",
                    "kind": "actor",
                }
            ],
            "features": [
                {
                    "key": key,
                    "name": first_line,
                    "source": "public.events.insert",
                    "how_it_works": first_line,
                    "match_intent": "Infer a concrete source table and operation from the schema and technical tasks.",
                    "subject_state_analysis": {
                        "lifecycle_subject": "user",
                        "subject_id_path": "id",
                        "action_target_path": "id",
                        "state": None,
                        "record_predicates": [],
                        "analysis_notes": "Fallback delta produced due to LLM response parsing error.",
                    },
                }
            ],
        }
    )


async def generate_engine_delta_with_llm(
    *,
    llm: LLMClient,
    technical_execution: dict[str, str],
    plan_path: Path,
    codebase_path: Path,
    existing_engine: EngineDocument,
    registry_features: list[dict[str, Any]] | None = None,
    bias_feature_name: str | None = None,
) -> EngineDocument:
    """
    Generate an engine.yaml delta with the LLM.

    The response is expected to be JSON matching EngineDocument shape.
    """
    context_parts: list[str] = []
    for key in (
        "overview",
        "what_we_building",
        "tasks",
        "data_triggers",
        "success_metrics",
        "next_build",
        "exact_logic",
    ):
        value = (technical_execution.get(key) or "").strip()
        if value:
            context_parts.append(f"## {key}\n{value}")
    execution_context = "\n\n".join(context_parts) if context_parts else "(No technical execution context provided.)"

    schema_source, schema_context = _load_schema_context(codebase_path)

    registry_context = _format_registry_features_for_prompt(registry_features or [])
    engine_context = format_engine_summary(existing_engine)
    bias_note = f"\nPrefer feature key/name around: {bias_feature_name}" if bias_feature_name else ""

    prompt = f"""You are a growth engineering system planner.

Return ONLY JSON (no markdown) for an ENGINE DELTA object that will be merged by key.
The target file is skene/engine.yaml.

Rules:
1) Output JSON object with keys: version, subjects, features.
2) Include complete objects for each subject/feature you output (not partial patches).
3) Keys are stable identifiers. Reuse existing keys for updates; create new keys for new entries.
4) `features[].action` is OPTIONAL.
   - Include `action` ONLY when a database-trigger/cloud action is needed.
   - Omit `action` when code change alone is enough.
5) `features[].source` must be schema.table.operation (operation in insert/update/delete), e.g. public.documents.insert.
6) Keep version=1.

Required shape:
{{
  "version": 1,
  "subjects": [{{"key":"...", "table":"schema.table", "kind":"actor"}}],
  "features": [
    {{
      "key": "snake_case_key",
      "name": "Human Name",
      "source": "schema.table.insert",
      "how_it_works": "short explanation",
      "action": {{"use":"email", "config":{{...}}}},  // optional
      "match_intent": "table/column matching hint",
      "subject_state_analysis": {{
        "lifecycle_subject": "subject key",
        "subject_id_path": "id",
        "action_target_path": "owner_id",
        "state": null,
        "record_predicates": [],
        "analysis_notes": "..."
      }}
    }}
  ]
}}

Current engine context:
{engine_context}

Registry context:
{registry_context}

Project root: {codebase_path}
Plan path: {plan_path}

Technical execution:
{execution_context}

Database schema (optional):
Source: {schema_source}
{schema_context}
{bias_note}
"""

    try:
        response = await run_with_progress(llm.generate_content(prompt))
    except Exception as exc:
        warning(f"Engine delta generation failed, using fallback delta: {exc}")
        return _fallback_engine_delta(technical_execution, bias_feature_name=bias_feature_name)

    try:
        return parse_engine_delta_response(response or "")
    except Exception as exc:
        warning(f"Failed to parse engine delta JSON from LLM, using fallback: {exc}")
        return _fallback_engine_delta(technical_execution, bias_feature_name=bias_feature_name)
