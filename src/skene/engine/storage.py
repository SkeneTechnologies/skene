"""
Engine YAML storage and transformation utilities.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

SOURCE_PATTERN = re.compile(
    r"^(?P<schema>[a-zA-Z_][a-zA-Z0-9_]*)\.(?P<table>[a-zA-Z_][a-zA-Z0-9_]*)\.(?P<op>insert|update|delete)$",
    re.IGNORECASE,
)


class EngineAction(BaseModel):
    """Optional action metadata used by cloud/runtime execution."""

    model_config = ConfigDict(extra="ignore")

    use: str = Field(..., description="Action handler identifier (for example: email, webhook, queue).")
    config: dict[str, Any] = Field(default_factory=dict, description="Action-specific configuration payload.")


class SubjectStateAnalysis(BaseModel):
    """Subject-state analysis metadata for a feature."""

    model_config = ConfigDict(extra="ignore")

    lifecycle_subject: str | None = Field(default=None, description="Subject key used for lifecycle ownership.")
    subject_id_path: str | None = Field(default=None, description="Record path used as the subject identifier.")
    action_target_path: str | None = Field(default=None, description="Record path targeted by the action.")
    state: Any | None = Field(default=None, description="Optional state snapshot used by the feature.")
    record_predicates: list[Any] = Field(
        default_factory=list,
        description="Optional predicates used to filter matching records.",
    )
    analysis_notes: str | None = Field(default=None, description="Freeform notes explaining matching assumptions.")


class EngineSubject(BaseModel):
    """A subject definition in engine.yaml."""

    model_config = ConfigDict(extra="ignore")

    key: str = Field(..., description="Stable unique subject key.")
    table: str = Field(..., description="Database table for this subject (schema.table).")
    kind: str = Field(..., description="Subject role/category such as actor or entity.")


class EngineFeature(BaseModel):
    """A feature definition in engine.yaml."""

    model_config = ConfigDict(extra="ignore")

    key: str = Field(..., description="Stable unique feature key.")
    name: str = Field(..., description="Human-readable feature name.")
    source: str = Field(..., description="Trigger source in schema.table.operation form.")
    how_it_works: str = Field(..., description="Short explanation of the feature behavior.")
    match_intent: str = Field(default="", description="Hints for source and field matching logic.")
    subject_state_analysis: SubjectStateAnalysis = Field(
        default_factory=SubjectStateAnalysis,
        description="Subject-state mapping details for lifecycle and targeting.",
    )
    action: EngineAction | None = Field(default=None, description="Optional action definition for runtime execution.")


class EngineDocument(BaseModel):
    """Top-level engine.yaml document."""

    model_config = ConfigDict(extra="ignore")

    version: int = Field(default=1, description="Engine schema version.")
    subjects: list[EngineSubject] = Field(default_factory=list, description="Declared subjects in engine.yaml.")
    features: list[EngineFeature] = Field(default_factory=list, description="Declared features in engine.yaml.")


def default_engine_dir(project_root: Path) -> Path:
    """Return the canonical skene engine directory under a project root."""
    return project_root / "skene"


def default_engine_path(project_root: Path) -> Path:
    """Return the canonical engine.yaml path under a project root."""
    return default_engine_dir(project_root) / "engine.yaml"


def ensure_engine_dir(project_root: Path) -> Path:
    """Ensure the skene engine directory exists."""
    engine_dir = default_engine_dir(project_root)
    engine_dir.mkdir(parents=True, exist_ok=True)
    return engine_dir


def _validate_unique_keys(doc: EngineDocument) -> EngineDocument:
    subject_keys = [s.key for s in doc.subjects]
    feature_keys = [f.key for f in doc.features]

    duplicate_subjects = sorted({k for k in subject_keys if subject_keys.count(k) > 1})
    if duplicate_subjects:
        raise ValueError(f"Duplicate subject key(s) in engine.yaml: {', '.join(duplicate_subjects)}")

    duplicate_features = sorted({k for k in feature_keys if feature_keys.count(k) > 1})
    if duplicate_features:
        raise ValueError(f"Duplicate feature key(s) in engine.yaml: {', '.join(duplicate_features)}")

    return doc


def empty_engine_document() -> EngineDocument:
    """Return an empty engine document."""
    return EngineDocument(version=1, subjects=[], features=[])


def _assert_within_project_root(engine_path: Path, project_root: Path | None) -> None:
    """Ensure an engine path remains within the resolved project root."""
    if project_root is None:
        return
    resolved_root = project_root.resolve()
    resolved_engine_path = engine_path.resolve()
    if not resolved_engine_path.is_relative_to(resolved_root):
        raise ValueError(f"Engine path escapes project root: {engine_path}")


def normalize_engine_payload(payload: dict[str, Any]) -> EngineDocument:
    """Normalize an untrusted payload into a validated engine document."""
    if not isinstance(payload, dict):
        raise ValueError("Engine payload must be a JSON/YAML object.")

    if "engine" in payload and isinstance(payload["engine"], dict):
        payload = payload["engine"]

    normalized = {
        "version": payload.get("version", 1),
        "subjects": payload.get("subjects") or [],
        "features": payload.get("features") or [],
    }
    doc = EngineDocument.model_validate(normalized)
    return _validate_unique_keys(doc)


def load_engine_document(engine_path: Path, *, project_root: Path | None = None) -> EngineDocument:
    """Load engine.yaml from disk, returning an empty document if it does not exist."""
    _assert_within_project_root(engine_path, project_root)
    if not engine_path.exists():
        return empty_engine_document()

    raw = yaml.safe_load(engine_path.read_text(encoding="utf-8"))
    if raw is None:
        return empty_engine_document()
    if not isinstance(raw, dict):
        raise ValueError(f"Engine file must contain a top-level object: {engine_path}")
    return normalize_engine_payload(raw)


def write_engine_document(engine_path: Path, doc: EngineDocument, *, project_root: Path | None = None) -> Path:
    """Write a validated engine document to engine.yaml."""
    _assert_within_project_root(engine_path, project_root)
    validated = _validate_unique_keys(doc)
    engine_path.parent.mkdir(parents=True, exist_ok=True)
    data = validated.model_dump(mode="json")
    rendered = yaml.safe_dump(data, sort_keys=False, default_flow_style=False)
    engine_path.write_text(rendered, encoding="utf-8")
    return engine_path


def write_new_features_sidecar(
    engine_path: Path,
    features: list[EngineFeature],
    *,
    project_root: Path | None = None,
) -> Path:
    """
    Write ``new-features.yaml`` beside ``engine_path``.

    The file body is a pretty-printed JSON array of feature objects (JSON is
    valid YAML 1.2) listing the latest planned features from a single run.
    """
    out = engine_path.parent / "new-features.yaml"
    _assert_within_project_root(out, project_root)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = [f.model_dump(mode="json") for f in features]
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out


def merge_engine_documents(existing: EngineDocument, delta: EngineDocument) -> EngineDocument:
    """Merge delta subjects/features into an existing engine document by key."""
    subjects_by_key = {item.key: item for item in existing.subjects}
    for item in delta.subjects:
        subjects_by_key[item.key] = item

    features_by_key = {item.key: item for item in existing.features}
    for item in delta.features:
        features_by_key[item.key] = item

    merged = EngineDocument(
        version=max(existing.version, delta.version, 1),
        subjects=sorted(subjects_by_key.values(), key=lambda x: x.key),
        features=sorted(features_by_key.values(), key=lambda x: x.key),
    )
    return _validate_unique_keys(merged)


def _strip_code_fences(value: str) -> str:
    s = value.strip()
    if s.startswith("```"):
        lines = s.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    return s


def parse_engine_delta_response(response_text: str) -> EngineDocument:
    """Parse an LLM JSON response into a validated engine document delta."""
    cleaned = _strip_code_fences(response_text)
    payload = json.loads(cleaned)
    return normalize_engine_payload(payload)


def format_engine_summary(doc: EngineDocument) -> str:
    """Format a compact summary of current engine subjects/features for prompts."""
    if not doc.subjects and not doc.features:
        return "No existing engine subjects or features are defined yet."

    lines: list[str] = [
        "Existing engine state:",
        f"- subjects: {len(doc.subjects)}",
        f"- features: {len(doc.features)}",
    ]

    if doc.subjects:
        lines.append("Subjects:")
        for s in doc.subjects:
            lines.append(f"- {s.key}: {s.table} ({s.kind})")

    if doc.features:
        lines.append("Features:")
        for f in doc.features:
            action_part = f", action={f.action.use}" if f.action else ""
            lines.append(f"- {f.key}: {f.source}{action_part}")

    return "\n".join(lines)


def parse_source_to_db_event(source: str) -> tuple[str, str, str] | None:
    """
    Parse source string `schema.table.operation` into a DB event tuple.

    Returns:
        (schema, table, operation_upper) when valid, else None.
    """
    raw = (source or "").strip()
    match = SOURCE_PATTERN.match(raw)
    if not match:
        return None
    return (
        match.group("schema"),
        match.group("table"),
        match.group("op").upper(),
    )


def _extract_properties(feature: EngineFeature) -> list[str]:
    ssa = feature.subject_state_analysis
    candidates = [
        (ssa.subject_id_path or "").strip(),
        (ssa.action_target_path or "").strip(),
    ]
    props: list[str] = []
    for candidate in candidates:
        if not candidate:
            continue
        props.append(candidate.split(".")[-1])
    deduped = list(dict.fromkeys([p for p in props if p]))
    return deduped or ["id"]


def _sanitize_identifier(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_]+", "_", (value or "").lower()).strip("_")
    return cleaned or "feature"


def engine_features_to_loop_definitions(doc: EngineDocument) -> list[dict[str, Any]]:
    """
    Adapt engine.yaml features to the legacy loop schema consumed by build_migration_sql.

    Only features with `action` and a parseable source are converted.
    """
    converted: list[dict[str, Any]] = []

    for feature in doc.features:
        if feature.action is None:
            continue
        parsed = parse_source_to_db_event(feature.source)
        if not parsed:
            continue
        schema, table, operation = parsed

        loop_id = _sanitize_identifier(feature.key)
        telemetry = {
            "type": "supabase",
            "action_name": _sanitize_identifier(feature.key),
            "schema": schema,
            "table": table,
            "operation": operation,
            "description": feature.how_it_works,
            "properties": _extract_properties(feature),
        }
        converted.append(
            {
                "loop_id": loop_id,
                "name": feature.name,
                "requirements": {"telemetry": [telemetry]},
            }
        )

    return converted


def collect_engine_trigger_events(doc: EngineDocument) -> list[str]:
    """Return unique trigger events (`schema.table.operation`) for actionable engine features."""
    events: list[str] = []
    for feature in doc.features:
        if feature.action is None:
            continue
        parsed = parse_source_to_db_event(feature.source)
        if not parsed:
            continue
        schema, table, operation = parsed
        events.append(f"{schema.lower()}.{table.lower()}.{operation.lower()}")
    return list(dict.fromkeys(events))
