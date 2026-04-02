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

    use: str
    config: dict[str, Any] = Field(default_factory=dict)


class SubjectStateAnalysis(BaseModel):
    """Subject-state analysis metadata for a feature."""

    model_config = ConfigDict(extra="ignore")

    lifecycle_subject: str | None = None
    subject_id_path: str | None = None
    action_target_path: str | None = None
    state: Any | None = None
    record_predicates: list[Any] = Field(default_factory=list)
    analysis_notes: str | None = None


class EngineSubject(BaseModel):
    """A subject definition in engine.yaml."""

    model_config = ConfigDict(extra="ignore")

    key: str
    table: str
    kind: str


class EngineFeature(BaseModel):
    """A feature definition in engine.yaml."""

    model_config = ConfigDict(extra="ignore")

    key: str
    name: str
    source: str
    how_it_works: str
    match_intent: str = ""
    subject_state_analysis: SubjectStateAnalysis = Field(default_factory=SubjectStateAnalysis)
    action: EngineAction | None = None


class EngineDocument(BaseModel):
    """Top-level engine.yaml document."""

    model_config = ConfigDict(extra="ignore")

    version: int = 1
    subjects: list[EngineSubject] = Field(default_factory=list)
    features: list[EngineFeature] = Field(default_factory=list)


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


def load_engine_document(engine_path: Path) -> EngineDocument:
    """Load engine.yaml from disk, returning an empty document if it does not exist."""
    if not engine_path.exists():
        return empty_engine_document()

    raw = yaml.safe_load(engine_path.read_text(encoding="utf-8"))
    if raw is None:
        return empty_engine_document()
    if not isinstance(raw, dict):
        raise ValueError(f"Engine file must contain a top-level object: {engine_path}")
    return normalize_engine_payload(raw)


def write_engine_document(engine_path: Path, doc: EngineDocument) -> Path:
    """Write a validated engine document to engine.yaml."""
    validated = _validate_unique_keys(doc)
    engine_path.parent.mkdir(parents=True, exist_ok=True)
    data = validated.model_dump(mode="json")
    rendered = yaml.safe_dump(data, sort_keys=False, default_flow_style=False)
    engine_path.write_text(rendered, encoding="utf-8")
    return engine_path


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
        _, table, operation = parsed

        loop_id = _sanitize_identifier(feature.key)
        telemetry = {
            "type": "supabase",
            "action_name": _sanitize_identifier(feature.key),
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
    """Return unique trigger events (`table.operation`) for actionable engine features."""
    events: list[str] = []
    for feature in doc.features:
        if feature.action is None:
            continue
        parsed = parse_source_to_db_event(feature.source)
        if not parsed:
            continue
        _, table, operation = parsed
        events.append(f"{table.lower()}.{operation.lower()}")
    return list(dict.fromkeys(events))
