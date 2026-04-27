"""
User-journey compiler.

Reads ``schema.yaml`` (introspected schema), ``growth-manifest.json`` (current
features + opportunities), and ``engine.yaml`` (planned features) and produces
``skene/user-journey.yaml`` — a ``skene_compiled_state_machine`` document.

The output is assembled deterministically where possible:
- top-level metadata (``format``, ``version``, ``exported_at``)
- ``definitions[]`` derived from engine subjects + canonical 5-stage lifecycle
- ``schema_analysis.lifecycle_stages`` (canonical)

The body the LLM owns:
- ``compiled_features[]`` — one entry per engine feature, enriched with
  conditions, state_effects, and trigger metadata
- ``schema_analysis.ttv_journey_by_subject[]`` — ordered milestone/UI nodes,
  value points, and ordered edges with optional data-change narratives.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from skene.engine.storage import EngineDocument, load_engine_document
from skene.llm import LLMClient
from skene.output import status, warning

OUTPUT_FORMAT = "skene_compiled_state_machine"
OUTPUT_VERSION = "2026.04.22"

CANONICAL_STAGES: list[dict[str, str]] = [
    {"key": "signup", "name": "Signup", "description": "Account and identity creation"},
    {"key": "activation", "name": "Activation", "description": "Setup and first meaningful actions"},
    {"key": "engagement", "name": "Engagement", "description": "Core product usage"},
    {"key": "monetization", "name": "Monetization", "description": "Revenue and upgrades"},
    {"key": "retention", "name": "Retention", "description": "Ongoing usage and expansion"},
]

CANONICAL_TRANSITIONS: dict[str, list[str]] = {
    "signup": ["activation"],
    "activation": ["engagement"],
    "engagement": ["monetization"],
    "monetization": ["retention"],
    "retention": [],
}

LIFECYCLE_STAGES: list[dict[str, Any]] = [
    {
        "id": f"stage_{stage['key']}",
        "label": stage["name"],
        "order": idx,
        "description": stage["description"],
    }
    for idx, stage in enumerate(CANONICAL_STAGES)
]

_SOURCE_RE = re.compile(
    r"^(?P<schema>[a-zA-Z_][a-zA-Z0-9_]*)\.(?P<table>[a-zA-Z_][a-zA-Z0-9_]*)\.(?P<op>insert|update|delete)$",
    re.IGNORECASE,
)

_FENCE_RE = re.compile(r"```(?:json|yaml|ya?ml)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_TRAILING_COMMA_RE = re.compile(r",(\s*[}\]])")


def _strip_fences(text: str) -> str:
    """If the response is wrapped in ```...``` fences, return the inner body."""
    m = _FENCE_RE.search(text)
    return m.group(1).strip() if m else text


def _balanced_object_slice(text: str) -> str | None:
    """Return the first balanced top-level ``{...}`` block, ignoring braces in strings.

    Handles escaped quotes inside JSON strings so braces inside string values
    don't trip the matcher.
    """
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _salvage_truncated_object(text: str) -> str | None:
    """Try to salvage a truncated JSON object by closing open structures.

    Walks the text, tracks open ``{``/``[``/string state, and on the way
    builds a closed-off version of the prefix. If the input is missing the
    closing fence/braces (token-limit truncation), this returns a syntactically
    valid JSON string formed by:
    - dropping any in-progress incomplete property after the last well-formed
      ``,`` boundary at the current depth, and
    - appending the missing closers.

    Returns ``None`` if no opening ``{`` was found.
    """
    start = text.find("{")
    if start == -1:
        return None

    stack: list[str] = []
    in_string = False
    escape = False
    last_safe = -1

    i = start
    while i < len(text):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            stack.append("}")
        elif ch == "[":
            stack.append("]")
        elif ch == "}" or ch == "]":
            if stack and stack[-1] == ch:
                stack.pop()
            else:
                break
            if not stack:
                return text[start : i + 1]
        elif ch == "," and stack:
            last_safe = i
        i += 1

    if not stack:
        return None

    if last_safe > start:
        prefix = text[start:last_safe]
    else:
        prefix = text[start:i]
        if in_string:
            prefix += '"'

    closers = "".join(reversed(stack))
    return prefix + closers


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Best-effort extraction of a JSON object from a noisy LLM response.

    Strategies (in order):
    1. Direct ``json.loads`` after stripping whitespace and code fences.
    2. Slice the first balanced ``{...}`` and parse it.
    3. Strip trailing commas before ``]``/``}`` and try again.
    4. Salvage a truncated object by closing open structures (last resort).
    """
    text = (text or "").strip()
    if not text:
        return None

    candidates: list[str] = []
    body = _strip_fences(text).strip()
    candidates.append(body)
    sliced = _balanced_object_slice(body)
    if sliced and sliced != body:
        candidates.append(sliced)

    for candidate in list(candidates):
        cleaned = _TRAILING_COMMA_RE.sub(r"\1", candidate)
        if cleaned != candidate:
            candidates.append(cleaned)

    salvaged = _salvage_truncated_object(body)
    if salvaged:
        candidates.append(salvaged)
        cleaned = _TRAILING_COMMA_RE.sub(r"\1", salvaged)
        if cleaned != salvaged:
            candidates.append(cleaned)

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return None


def _dump_raw_response(output_path: Path, response: str, *, suffix: str = "raw.txt") -> Path:
    """Write the raw LLM response next to the journey output for debugging."""
    debug_path = output_path.with_name(f"{output_path.stem}.{suffix}")
    debug_path.parent.mkdir(parents=True, exist_ok=True)
    debug_path.write_text(response or "", encoding="utf-8")
    return debug_path


FEATURE_PROMPT = """\
You are compiling ONE growth feature into runtime conditions, state effects,
and short descriptions for a state-machine compiler.

Project: {project_name}
Description: {description}

Database schema (YAML — authoritative; only reference these tables/columns):
```yaml
{schema}
```

Engine subjects (use one of these ``key`` values for ``subject_type``):
```json
{subjects}
```

Engine feature to compile:
```json
{feature}
```

Return ONLY a single JSON object with this exact shape (no prose, no code fences,
no trailing commas):
{{
  "loop_key": "{feature_key}",
  "name": "{feature_name}",
  "source": "premade",
  "action_type": "analytics|database|queue|email|webhook",
  "subject_type": "<one engine subject key>",
  "subject_path": "id",
  "owner_type": "user|null",
  "owner_path": "owner_id|null",
  "cooldown_ms": null,
  "max_fires": null,
  "conditions": [
    {{"key": "currentState", "value": "signup", "operator": "eq"}}
  ],
  "state_effects": [
    {{"key": "events", "value": "loop_fired.{feature_key}", "operation": "record_event"}}
  ],
  "conditions_description": "Plain-language description of when this loop fires.",
  "effects_description": "Plain-language description of what this loop records or transitions."
}}

Hard rules:
- ``loop_key`` MUST equal exactly "{feature_key}".
- ``subject_type`` MUST be one of the engine subject keys above.
- Do NOT invent tables/columns; reference only what is in the schema.
- Keep ``conditions`` and ``state_effects`` short (1-4 entries each).
- Return ONLY the JSON object — nothing else.
"""


SUBJECT_JOURNEY_PROMPT = """\
You are compiling the *time-to-value journey* for ONE subject in a product.

Project: {project_name}
Description: {description}

Database schema (YAML — authoritative; only reference these tables/columns):
```yaml
{schema}
```

Subject to compile:
```json
{subject}
```

Return ONLY a single JSON object with this exact shape (no prose, no code fences,
no trailing commas):
{{
  "subject_id": "subject_{subject_key}",
  "subject_label": "<Subject Label>",
  "subject_table": "{subject_table}",
  "ordered_nodes": [
    {{
      "id": "<snake_case_id>",
      "kind": "milestone",
      "label": "Human Readable",
      "table": "<table only>",
      "schema": "<schema only>",
      "category": "signup|activation|engagement|monetization|retention",
      "subject_id": "subject_{subject_key}",
      "description": "What this milestone represents.",
      "event_type": "INSERT|UPDATE|DELETE",
      "trigger_event": "<schema>.<table>.<INSERT|UPDATE|DELETE>",
      "state_scope": "<SQL where clause or descriptor>",
      "lifecycle_stage_id": "stage_signup",
      "lifecycle": {{"stage_id": "stage_signup", "label": "Signup", "order": 0}}
    }},
    {{
      "id": "<snake_case_id>",
      "kind": "ui_step",
      "label": "Visits Some Page",
      "table": "_ui",
      "schema": "app",
      "category": "signup|activation|engagement|monetization|retention",
      "subject_id": "subject_{subject_key}",
      "description": "Pre-DB UI step.",
      "is_ui_only": true,
      "route": "/some/route",
      "component": "ComponentName"
    }}
  ],
  "value_nodes": [
    {{
      "id": "vp__<schema>_<table>",
      "kind": "value",
      "label": "Short Value Label",
      "table": "<schema.table>",
      "value_type": "creation|consumption|conversion",
      "description": "Why this represents value.",
      "subject_id": "subject_{subject_key}",
      "lifecycle_spot": "activation|engagement|retention",
      "time_to_value_label": "~12 min",
      "linked_from_node_id": "<ordered_node id>",
      "estimated_minutes": 12
    }}
  ],
  "ordered_edges": [
    {{
      "source": "subject_{subject_key}",
      "target": "<first node id>",
      "source_label": "<Subject>",
      "target_label": "<First Node Label>",
      "label": "First step",
      "is_required": true
    }},
    {{
      "source": "<node id>",
      "target": "<node id>",
      "source_label": "<Source Node Label>",
      "target_label": "<Target Node Label>",
      "label": "<edge action label>",
      "is_required": true,
      "data_change": {{
        "summary": "<short summary>",
        "narrative": "<2-4 sentence narrative referencing real columns>",
        "columns_changed": [
          {{"schema": "<schema>", "table": "<table>", "column": "<col>", "from": "NULL", "to": "now()"}}
        ]
      }}
    }}
  ]
}}

Hard rules:
- ``subject_id`` MUST be exactly "subject_{subject_key}".
- ``subject_table`` MUST be exactly "{subject_table}".
- Walk the subject through signup → activation → engagement → (monetization)
  → retention using ``kind: "milestone"`` for DB events and ``kind: "ui_step"``
  for pre-DB UI steps.
- ``value_nodes[].id`` MUST be of the form ``vp__<schema>_<table>`` and link
  back to a milestone via ``linked_from_node_id``.
- ``ordered_edges`` MUST chain the nodes in order; the first edge always goes
  from ``subject_{subject_key}`` to the first ordered node with label
  ``"First step"`` and ``is_required: true``.
- Include ``data_change`` blocks ONLY on edges that correspond to a real DB
  write; omit ``data_change`` entirely on UI-only edges.
- ``lifecycle_stage_id`` MUST be one of ``stage_signup``, ``stage_activation``,
  ``stage_engagement``, ``stage_monetization``, ``stage_retention``.
- Aim for 4-10 ordered_nodes total. Keep the JSON minimal but complete.
- Return ONLY the JSON object — nothing else.
"""


@dataclass
class JourneyState:
    """Accumulated state for a single user-journey compilation run."""

    schema: dict[str, Any] = field(default_factory=dict)
    manifest: dict[str, Any] = field(default_factory=dict)
    engine: EngineDocument | None = None
    definitions: list[dict[str, Any]] = field(default_factory=list)
    compiled_features: list[dict[str, Any]] = field(default_factory=list)
    schema_analysis: dict[str, Any] = field(default_factory=dict)
    document: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping at {path}")
    return data


def _load_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return data


# ---------------------------------------------------------------------------
# Deterministic builders
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(UTC).microsecond // 1000:03d}Z"


def _compiled_at() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f%z").replace("+0000", "+00:00")


def build_definitions(engine: EngineDocument) -> list[dict[str, Any]]:
    """Build the ``definitions[]`` block deterministically from engine subjects.

    Each subject becomes a 5-stage state machine using the canonical lifecycle
    and transition map.
    """
    if not engine.subjects:
        return []

    out: list[dict[str, Any]] = []
    for subject in engine.subjects:
        out.append(
            {
                "subject_type": subject.key,
                "subject_table": subject.table,
                "stages": [dict(s) for s in CANONICAL_STAGES],
                "initial_stage": "signup",
                "transitions": {k: list(v) for k, v in CANONICAL_TRANSITIONS.items()},
                "transitions_description": (
                    f"{subject.key} progresses through the canonical 5-stage lifecycle: "
                    "signup → activation → engagement → monetization → retention."
                ),
                "compiled_at": _compiled_at(),
                "source": None,
            }
        )
    return out


def _trigger_metadata_from_source(source: str) -> dict[str, Any]:
    """Derive trigger_event_schema/table/operation + synthetic trigger_name."""
    m = _SOURCE_RE.match(source or "")
    if not m:
        return {
            "trigger_id": str(uuid.uuid4()),
            "trigger_name": None,
            "trigger_event_schema": None,
            "trigger_event_table": None,
            "trigger_operation": None,
            "trigger_exists_in_customer_db": False,
        }
    schema = m.group("schema")
    table = m.group("table")
    op = m.group("op").upper()
    return {
        "trigger_id": str(uuid.uuid4()),
        "trigger_name": f"skene_growth_trg_{table}_{op.lower()}",
        "trigger_event_schema": schema,
        "trigger_event_table": table,
        "trigger_operation": op,
        "trigger_exists_in_customer_db": False,
    }


def _enrich_compiled_features(
    llm_features: list[dict[str, Any]],
    engine: EngineDocument,
) -> list[dict[str, Any]]:
    """Stamp each compiled feature with deterministic id, trigger metadata, and
    matcher defaults. Aligns each entry with the engine feature by ``loop_key``.
    """
    by_key = {f.key: f for f in engine.features}
    enriched: list[dict[str, Any]] = []

    for entry in llm_features:
        if not isinstance(entry, dict):
            continue
        loop_key = entry.get("loop_key")
        engine_feat = by_key.get(loop_key) if isinstance(loop_key, str) else None
        if engine_feat is None:
            continue

        trigger_meta = _trigger_metadata_from_source(engine_feat.source)
        merged: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "loop_key": engine_feat.key,
            "name": entry.get("name") or engine_feat.name,
            "source": entry.get("source") or "premade",
            "action_type": entry.get("action_type") or "database",
            "subject_type": entry.get("subject_type"),
            "subject_path": entry.get("subject_path") or "id",
            "owner_type": entry.get("owner_type"),
            "owner_path": entry.get("owner_path"),
            "cooldown_ms": entry.get("cooldown_ms"),
            "max_fires": entry.get("max_fires"),
            "conditions": entry.get("conditions") or [],
            "state_effects": entry.get("state_effects") or [],
            "conditions_description": entry.get("conditions_description") or "",
            "effects_description": entry.get("effects_description") or "",
            "compiled_at": _compiled_at(),
            "resolved_tool_key": entry.get("resolved_tool_key"),
            "resolved_tool_confidence": entry.get("resolved_tool_confidence"),
            "matcher_mode": "deterministic",
            "matcher_min_confidence": 0.8,
            "tool_min_confidence": 0.4,
            **trigger_meta,
        }
        enriched.append(merged)

    return enriched


def _schema_for_prompt(schema: dict[str, Any], max_chars: int = 14_000) -> str:
    compact = {
        "tables": [
            {
                "name": t.get("name"),
                "description": t.get("description") or None,
                "columns": [
                    {
                        "name": c.get("name"),
                        "type": c.get("type"),
                        "primary_key": c.get("primary_key", False),
                        "nullable": c.get("nullable"),
                    }
                    for c in (t.get("columns") or [])
                    if isinstance(c, dict) and c.get("name")
                ],
                "relationships": t.get("relationships") or [],
            }
            for t in (schema.get("tables") or [])
            if isinstance(t, dict) and t.get("name")
        ]
    }
    rendered = yaml.safe_dump(compact, sort_keys=False, default_flow_style=False)
    if len(rendered) > max_chars:
        rendered = rendered[:max_chars] + "\n# [truncated]"
    return rendered


def _feature_for_prompt(feat: Any) -> dict[str, Any]:
    return {
        "key": feat.key,
        "name": feat.name,
        "source": feat.source,
        "how_it_works": feat.how_it_works,
        "match_intent": feat.match_intent,
        "subject_state_analysis": feat.subject_state_analysis.model_dump(mode="json"),
    }


def _subjects_for_prompt(engine: EngineDocument) -> list[dict[str, str]]:
    return [{"key": s.key, "table": s.table, "kind": s.kind} for s in engine.subjects]


def _empty_journey_document(engine: EngineDocument) -> dict[str, Any]:
    """Build a minimal, LLM-free document used when there are no engine
    features to compile."""
    return {
        "format": OUTPUT_FORMAT,
        "version": OUTPUT_VERSION,
        "exported_at": _utc_now_iso(),
        "definitions": build_definitions(engine),
        "compiled_features": [],
        "schema_analysis": {
            "analysis_id": str(uuid.uuid4()),
            "updated_at": _utc_now_iso(),
            "lifecycle_stages": [dict(s) for s in LIFECYCLE_STAGES],
            "ttv_journey_by_subject": [],
        },
    }


_RETRY_REMINDER = (
    "\n\nIMPORTANT: Your previous response could not be parsed as JSON. "
    "Return ONLY a single JSON object, no prose, no markdown fences, no trailing commas. "
    "It must contain exactly the keys ``compiled_features`` and ``ttv_journey_by_subject``."
)


async def _generate_and_parse(
    llm: LLMClient,
    prompt: str,
    *,
    max_attempts: int = 2,
) -> tuple[dict[str, Any] | None, str]:
    """Call the LLM and try to extract a JSON object, retrying once on failure."""
    last_response = ""
    current_prompt = prompt
    for attempt in range(1, max_attempts + 1):
        try:
            last_response = await llm.generate_content(current_prompt) or ""
        except Exception as e:
            warning(f"user-journey: LLM call failed on attempt {attempt}: {e}")
            current_prompt = prompt + _RETRY_REMINDER
            continue

        parsed = _extract_json_object(last_response)
        if parsed is not None:
            return parsed, last_response

        warning(
            f"user-journey: could not parse JSON on attempt {attempt} "
            f"(response length={len(last_response)})"
        )
        current_prompt = prompt + _RETRY_REMINDER

    return None, last_response


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def compile_user_journey(
    *,
    schema_path: Path,
    manifest_path: Path,
    engine_path: Path,
    output_path: Path,
    llm: LLMClient,
    project_root: Path | None = None,
) -> JourneyState:
    """
    Compile ``user-journey.yaml`` from schema + manifest + engine artifacts.

    On LLM failure or invalid response, the previous user-journey.yaml is
    preserved (the function raises so the caller can record a failed outcome).
    """
    state = JourneyState()
    state.schema = _load_yaml(schema_path)
    state.manifest = _load_json(manifest_path)
    state.engine = load_engine_document(engine_path, project_root=project_root)

    state.definitions = build_definitions(state.engine)

    if not state.engine.features:
        warning("user-journey: engine.yaml has no features; writing minimal document.")
        state.document = _empty_journey_document(state.engine)
        _write_document(output_path, state.document, project_root=project_root)
        return state

    schema_block = _schema_for_prompt(state.schema)
    subjects_block = json.dumps(_subjects_for_prompt(state.engine), indent=2)
    project_name = state.manifest.get("project_name") or "unknown"
    description = state.manifest.get("description") or "(no description)"

    raw_features: list[dict[str, Any]] = []
    failed_features: list[str] = []
    total_features = len(state.engine.features)
    status(f"Compiling user-journey.yaml: {total_features} feature(s) + {len(state.engine.subjects)} subject(s)")

    for idx, feat in enumerate(state.engine.features, start=1):
        prompt = FEATURE_PROMPT.format(
            project_name=project_name,
            description=description,
            schema=schema_block,
            subjects=subjects_block,
            feature=json.dumps(_feature_for_prompt(feat), indent=2),
            feature_key=feat.key,
            feature_name=feat.name,
        )
        status(f"  [{idx}/{total_features}] feature {feat.key}")
        parsed, raw = await _generate_and_parse(llm, prompt)
        if parsed is None:
            _dump_raw_response(output_path, raw or "", suffix=f"feature.{feat.key}.raw.txt")
            failed_features.append(feat.key)
            continue
        parsed.setdefault("loop_key", feat.key)
        raw_features.append(parsed)

    if not raw_features:
        raise ValueError(
            f"Compiled-features step produced no parsable feature objects "
            f"(failed: {', '.join(failed_features) or 'none'})."
        )
    if failed_features:
        warning(f"user-journey: dropped {len(failed_features)} feature(s) that failed to parse: {', '.join(failed_features)}")

    raw_subjects: list[dict[str, Any]] = []
    failed_subjects: list[str] = []
    total_subjects = len(state.engine.subjects)
    for idx, subj in enumerate(state.engine.subjects, start=1):
        prompt = SUBJECT_JOURNEY_PROMPT.format(
            project_name=project_name,
            description=description,
            schema=schema_block,
            subject=json.dumps({"key": subj.key, "table": subj.table, "kind": subj.kind}, indent=2),
            subject_key=subj.key,
            subject_table=subj.table,
        )
        status(f"  [{idx}/{total_subjects}] subject {subj.key}")
        parsed, raw = await _generate_and_parse(llm, prompt)
        if parsed is None:
            _dump_raw_response(output_path, raw or "", suffix=f"subject.{subj.key}.raw.txt")
            failed_subjects.append(subj.key)
            continue
        parsed.setdefault("subject_id", f"subject_{subj.key}")
        parsed.setdefault("subject_table", subj.table)
        parsed.setdefault("ordered_nodes", [])
        parsed.setdefault("value_nodes", [])
        parsed.setdefault("ordered_edges", [])
        raw_subjects.append(parsed)

    if failed_subjects:
        warning(f"user-journey: dropped {len(failed_subjects)} subject(s) that failed to parse: {', '.join(failed_subjects)}")

    state.compiled_features = _enrich_compiled_features(raw_features, state.engine)
    state.schema_analysis = {
        "analysis_id": str(uuid.uuid4()),
        "updated_at": _utc_now_iso(),
        "lifecycle_stages": [dict(s) for s in LIFECYCLE_STAGES],
        "ttv_journey_by_subject": raw_subjects,
    }

    state.document = {
        "format": OUTPUT_FORMAT,
        "version": OUTPUT_VERSION,
        "exported_at": _utc_now_iso(),
        "definitions": state.definitions,
        "compiled_features": state.compiled_features,
        "schema_analysis": state.schema_analysis,
    }

    _write_document(output_path, state.document, project_root=project_root)
    return state


def _write_document(path: Path, doc: dict[str, Any], *, project_root: Path | None) -> Path:
    if project_root is not None:
        resolved_root = project_root.resolve()
        if not path.resolve().is_relative_to(resolved_root):
            raise ValueError(f"user-journey path escapes project root: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = yaml.safe_dump(doc, sort_keys=False, default_flow_style=False)
    path.write_text(rendered, encoding="utf-8")
    return path
