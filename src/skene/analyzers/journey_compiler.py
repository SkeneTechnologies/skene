"""
User-journey compiler.

Reads ``schema.yaml`` (introspected schema) and ``growth-manifest.json``
(current features + growth opportunities), optionally augmented by
``engine.yaml`` (planned features), and produces ``skene/user-journey.yaml``
— a ``skene_compiled_state_machine`` document.

The output is assembled deterministically where possible:
- top-level metadata (``format``, ``version``, ``exported_at``)
- ``definitions[]`` derived from engine subjects + canonical 5-stage lifecycle
- ``schema_analysis.lifecycle_stages`` (canonical)

The body the LLM owns:
- ``schema_analysis.ttv_journey_by_subject[]`` — built from a single
  schema + growth-opportunities LLM call that emits a global Time-to-Value
  DAG (subjects, nodes, edges, valueProxies). The DAG is then validated
  and grouped per subject for the storage shape consumed by the visualiser.
- ``compiled_features[]`` — one entry per engine feature (only when an
  ``engine.yaml`` with features exists), enriched with conditions,
  state_effects, and trigger metadata.
"""

from __future__ import annotations

import json
import re
import uuid
from collections import defaultdict, deque
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


TTV_JOURNEY_PROMPT = """\
You are a database schema analyst for product-led growth. From the schema and
growth context below, output ONE Time-to-Value (TTV) journey as a directed
acyclic graph (DAG) of lifecycle milestones, scoped to one or more subjects
(entities that "take" the journey).

Project: {project_name}
Description: {description}

Database schema (YAML — authoritative; only reference these tables/columns):
```yaml
{schema}
```

Current growth features already shipping in the product:
```json
{current_features}
```

Growth opportunities the product wants to drive value from:
```json
{growth_opportunities}
```

Return ONLY a single JSON object with this exact shape (no prose, no code
fences, no trailing commas):
{{
  "lifecycleDataExplanation": "2–8 sentences for subjects[0]: cite schema + row events between lifecycle phases.",
  "subjects": [
    {{
      "id": "user",
      "table": "users",
      "schema": "public",
      "label": "User",
      "description": "Why this entity is the journey owner."
    }}
  ],
  "nodes": [
    {{
      "id": "signed_up",
      "label": "Signed Up",
      "subjectId": "user",
      "schema": "auth",
      "table": "users",
      "eventType": "INSERT",
      "category": "signup",
      "description": "Cohort definition: who the subjects ARE in this state.",
      "stateScope": "created_at >= now() - interval '7 days'"
    }}
  ],
  "edges": [
    {{
      "source": "signed_up",
      "target": "profile_completed",
      "label": "Completes profile",
      "isRequired": true,
      "dataChange": {{
        "summary": "profiles.completed_at set",
        "narrative": "1–4 sentences: what rows/columns change so the target state becomes true after the source state.",
        "columnHints": [
          {{"schema": "public", "table": "profiles", "column": "completed_at", "from": "NULL", "to": "now()"}}
        ],
        "assumptions": ""
      }}
    }}
  ],
  "valueProxies": [
    {{
      "table": "public.posts",
      "label": "First Post",
      "valueType": "creation",
      "description": "Why this surface represents realised value.",
      "linkedFromNodeId": "first_post_created",
      "lifecycleSpot": "engagement"
    }}
  ]
}}

Hard rules:
- Output ONE global graph; subject separation is via ``subjectId`` on nodes.
- Order ``subjects`` with the PRIMARY actor first — usually the end-user or
  core business entity the product is "about" (infer from FK hubs, naming,
  whether ``auth.users`` or a profiles/accounts/organizations table is the
  real journey owner).
- 4–18 milestone nodes total across ALL subjects. For huge schemas, merge
  peripheral tables into fewer user-meaningful steps; do not emit one node
  per internal/auth table.
- Every ``nodes[].subjectId`` MUST equal one of ``subjects[].id``.
- Only reference real schema/table/column names from the YAML above.
- ``category`` MUST be one of: signup, activation, engagement, monetization,
  retention.
- ``stateScope`` is REQUIRED on every node — a SQL WHERE-style fragment that
  defines which rows count as "in this state" (use cohort/time/status
  predicates like ``created_at``, ``status``, ``trial_ends_at``). Do not use
  per-session or ``auth.uid()`` filters. If nothing better fits, default to
  ``created_at >= now() - interval '7 days'``.
- Edges connect node id → node id only. The graph MUST be acyclic.
- Every edge MUST include ``dataChange`` with at least ``summary``
  (≤80 chars) and ``narrative`` (1–4 sentences). ``columnHints`` are 0–8
  entries; ``assumptions`` is optional.
- ``valueProxies[].valueType`` MUST be one of: creation, financial,
  consumption. ``linkedFromNodeId`` MUST reference an existing node id and
  pick the milestone where value is realised — not "first signup" unless
  value truly realises there. Use ``valueProxies: []`` if no clear value
  tables exist.
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


# ---------------------------------------------------------------------------
# TTV journey: spec validation + transform to storage shape
# ---------------------------------------------------------------------------

_VALID_CATEGORIES: set[str] = {"signup", "activation", "engagement", "monetization", "retention"}
_VALID_VALUE_TYPES: set[str] = {"creation", "financial", "consumption"}
_DEFAULT_STATE_SCOPE = "created_at >= now() - interval '7 days'"

_LIFECYCLE_BY_KEY: dict[str, dict[str, Any]] = {
    stage["key"]: {
        "stage_id": f"stage_{stage['key']}",
        "label": stage["name"],
        "order": idx,
    }
    for idx, stage in enumerate(CANONICAL_STAGES)
}


def _topo_sort(node_ids: list[str], edges: list[dict[str, Any]]) -> list[str]:
    """Kahn-style topological sort restricted to ``node_ids``.

    Falls back to the input order for any nodes left over (cycle defence).
    """
    indeg: dict[str, int] = {nid: 0 for nid in node_ids}
    out: dict[str, list[str]] = defaultdict(list)
    seen_pairs: set[tuple[str, str]] = set()
    for e in edges:
        s = e.get("source")
        t = e.get("target")
        if s in indeg and t in indeg and (s, t) not in seen_pairs:
            seen_pairs.add((s, t))
            out[s].append(t)
            indeg[t] += 1

    q: deque[str] = deque(nid for nid in node_ids if indeg[nid] == 0)
    order: list[str] = []
    while q:
        n = q.popleft()
        order.append(n)
        for m in out[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                q.append(m)

    if len(order) != len(node_ids):
        seen = set(order)
        order.extend(nid for nid in node_ids if nid not in seen)
    return order


def _validate_ttv_spec(spec: dict[str, Any]) -> None:
    """Apply the post-model validation checklist on the LLM output.

    Raises ``ValueError`` if the spec is unusable. Mutates ``spec`` in place
    to backfill defaults (``stateScope``, ``valueProxies``).
    """
    subjects = spec.get("subjects")
    nodes = spec.get("nodes")
    edges = spec.get("edges")
    if not isinstance(subjects, list) or not subjects:
        raise ValueError("ttv journey: 'subjects' must be a non-empty array")
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("ttv journey: 'nodes' must be a non-empty array")
    if not isinstance(edges, list) or not edges:
        raise ValueError("ttv journey: 'edges' must be a non-empty array")

    subject_ids: set[str] = set()
    for s in subjects:
        if not isinstance(s, dict) or not s.get("id"):
            raise ValueError("ttv journey: each subject needs an 'id'")
        subject_ids.add(str(s["id"]))

    node_ids: set[str] = set()
    for n in nodes:
        if not isinstance(n, dict) or not n.get("id"):
            raise ValueError("ttv journey: each node needs an 'id'")
        nid = str(n["id"])
        if nid in node_ids:
            raise ValueError(f"ttv journey: duplicate node id {nid!r}")
        node_ids.add(nid)
        if n.get("subjectId") not in subject_ids:
            raise ValueError(f"ttv journey: node {nid!r} subjectId not in subjects")
        if n.get("category") not in _VALID_CATEGORIES:
            n["category"] = "engagement"
        if not isinstance(n.get("stateScope"), str) or not n["stateScope"].strip():
            n["stateScope"] = _DEFAULT_STATE_SCOPE

    for e in edges:
        if not isinstance(e, dict):
            raise ValueError("ttv journey: edges must be objects")
        s, t = e.get("source"), e.get("target")
        if s not in node_ids or t not in node_ids:
            raise ValueError(f"ttv journey: edge {s!r}->{t!r} references unknown node id")
        dc = e.get("dataChange")
        if not isinstance(dc, dict) or not (dc.get("summary") and dc.get("narrative")):
            raise ValueError(f"ttv journey: edge {s}->{t} is missing dataChange.summary/narrative")

    indeg = {nid: 0 for nid in node_ids}
    out: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        out[e["source"]].append(e["target"])
        indeg[e["target"]] += 1
    q = deque([nid for nid, d in indeg.items() if d == 0])
    visited = 0
    while q:
        n = q.popleft()
        visited += 1
        for m in out[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                q.append(m)
    if visited != len(node_ids):
        raise ValueError("ttv journey: edge graph contains a cycle (must be a DAG)")

    proxies = spec.get("valueProxies")
    if proxies is None:
        spec["valueProxies"] = []
    elif not isinstance(proxies, list):
        raise ValueError("ttv journey: 'valueProxies' must be a list")
    else:
        for vp in proxies:
            if not isinstance(vp, dict):
                raise ValueError("ttv journey: each valueProxy must be an object")
            if vp.get("valueType") not in _VALID_VALUE_TYPES:
                raise ValueError(
                    f"ttv journey: valueProxy valueType {vp.get('valueType')!r} not in {_VALID_VALUE_TYPES}"
                )
            if vp.get("linkedFromNodeId") not in node_ids:
                raise ValueError(
                    f"ttv journey: valueProxy linkedFromNodeId {vp.get('linkedFromNodeId')!r} not in nodes"
                )


def _ttv_spec_to_subject_journeys(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Group the global TTV DAG into per-subject journey objects in the
    storage shape consumed by ``user-journey.yaml`` and the visualiser.
    """
    subjects = spec["subjects"]
    nodes_by_id = {str(n["id"]): n for n in spec["nodes"]}
    edges = spec["edges"]
    proxies = spec.get("valueProxies") or []

    journeys: list[dict[str, Any]] = []
    for subj in subjects:
        sid = str(subj["id"])
        subject_id = f"subject_{sid}"
        subj_node_ids = [nid for nid, n in nodes_by_id.items() if n.get("subjectId") == sid]
        if not subj_node_ids:
            continue

        within = [e for e in edges if e["source"] in subj_node_ids and e["target"] in subj_node_ids]
        order = _topo_sort(subj_node_ids, within)

        ordered_nodes: list[dict[str, Any]] = []
        for nid in order:
            n = nodes_by_id[nid]
            stage = n.get("category") or "engagement"
            schema_part = n.get("schema") or "public"
            table_part = n.get("table") or ""
            event_type = (n.get("eventType") or "INSERT").upper()
            trigger_event = f"{schema_part}.{table_part}.{event_type}".lower() if table_part else None
            ordered_nodes.append(
                {
                    "id": nid,
                    "kind": "milestone",
                    "label": n.get("label") or nid,
                    "schema": schema_part,
                    "table": table_part,
                    "category": stage,
                    "subject_id": subject_id,
                    "description": n.get("description") or "",
                    "event_type": event_type,
                    "trigger_event": trigger_event,
                    "state_scope": n.get("stateScope") or _DEFAULT_STATE_SCOPE,
                    "lifecycle_stage_id": f"stage_{stage}",
                    "lifecycle": dict(_LIFECYCLE_BY_KEY[stage]),
                }
            )

        value_nodes: list[dict[str, Any]] = []
        for vp in proxies:
            linked = vp.get("linkedFromNodeId")
            if linked not in subj_node_ids:
                continue
            tbl = str(vp.get("table") or "")
            if "." in tbl:
                schema_part, _, table_part = tbl.partition(".")
            else:
                schema_part, table_part = "public", tbl
            vp_id_basis = f"{schema_part}_{table_part}".strip("_") or linked
            value_nodes.append(
                {
                    "id": f"vp__{vp_id_basis}",
                    "kind": "value",
                    "label": vp.get("label") or tbl or linked,
                    "table": tbl,
                    "value_type": vp.get("valueType") or "creation",
                    "description": vp.get("description") or "",
                    "subject_id": subject_id,
                    "lifecycle_spot": vp.get("lifecycleSpot")
                    or (nodes_by_id[linked].get("category") if linked in nodes_by_id else "activation"),
                    "linked_from_node_id": linked,
                }
            )

        ordered_edges: list[dict[str, Any]] = []
        if order:
            first = order[0]
            ordered_edges.append(
                {
                    "source": subject_id,
                    "target": first,
                    "source_label": subj.get("label") or sid,
                    "target_label": nodes_by_id[first].get("label") or first,
                    "label": "First step",
                    "is_required": True,
                }
            )
        for e in within:
            dc = e.get("dataChange") or {}
            cols_changed: list[dict[str, Any]] = []
            for c in dc.get("columnHints") or []:
                if not isinstance(c, dict):
                    continue
                cols_changed.append(
                    {
                        "schema": c.get("schema"),
                        "table": c.get("table"),
                        "column": c.get("column"),
                        "from": c.get("from"),
                        "to": c.get("to"),
                    }
                )
            ordered_edges.append(
                {
                    "source": e["source"],
                    "target": e["target"],
                    "source_label": nodes_by_id[e["source"]].get("label") or e["source"],
                    "target_label": nodes_by_id[e["target"]].get("label") or e["target"],
                    "label": e.get("label") or dc.get("summary") or "",
                    "is_required": bool(e.get("isRequired", True)),
                    "data_change": {
                        "summary": dc.get("summary") or "",
                        "narrative": dc.get("narrative") or "",
                        "columns_changed": cols_changed,
                    },
                }
            )

        journeys.append(
            {
                "subject_id": subject_id,
                "subject_label": subj.get("label") or sid,
                "subject_table": subj.get("table") or "",
                "ordered_nodes": ordered_nodes,
                "value_nodes": value_nodes,
                "ordered_edges": ordered_edges,
            }
        )

    return journeys


def _growth_for_prompt(manifest: dict[str, Any]) -> tuple[str, str]:
    """Render compact JSON blocks for current features and growth opportunities."""
    current = []
    for f in manifest.get("current_growth_features") or []:
        if not isinstance(f, dict):
            continue
        current.append(
            {
                "feature_name": f.get("feature_name"),
                "detected_intent": f.get("detected_intent"),
                "growth_potential": f.get("growth_potential") or [],
            }
        )
    opps = []
    for o in manifest.get("growth_opportunities") or []:
        if not isinstance(o, dict):
            continue
        opps.append(
            {
                "feature_name": o.get("feature_name"),
                "description": o.get("description"),
                "priority": o.get("priority"),
            }
        )
    return (
        json.dumps(current, indent=2) if current else "[]",
        json.dumps(opps, indent=2) if opps else "[]",
    )


_JSON_RETRY_REMINDER = (
    "\n\nIMPORTANT: Your previous response could not be parsed as JSON. "
    "Return ONLY the single JSON object whose shape matches the template above "
    "for this ONE item (one compiled feature OR one subject journey — whichever "
    "this prompt asks for). "
    "Do not emit a wrapper object keyed by ``compiled_features``, ``schema_analysis``, "
    "or ``ttv_journey_by_subject``; output just that inner object. "
    "No prose, no markdown fences, no trailing commas."
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
            current_prompt = prompt + _JSON_RETRY_REMINDER
            continue

        parsed = _extract_json_object(last_response)
        if parsed is not None:
            return parsed, last_response

        warning(f"user-journey: could not parse JSON on attempt {attempt} (response length={len(last_response)})")
        current_prompt = prompt + _JSON_RETRY_REMINDER

    return None, last_response


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def _build_ttv_journey_by_subject(
    *,
    llm: LLMClient,
    schema: dict[str, Any],
    manifest: dict[str, Any],
    output_path: Path,
) -> tuple[list[dict[str, Any]], str]:
    """Run the single TTV-spec LLM call and convert its output to the
    per-subject storage shape.

    Returns ``(journeys, lifecycle_explanation)``. Raises ``ValueError`` if
    the LLM cannot produce a valid spec; the raw response is dumped next to
    the output for debugging.
    """
    schema_block = _schema_for_prompt(schema)
    current_block, opps_block = _growth_for_prompt(manifest)
    project_name = manifest.get("project_name") or "unknown"
    description = manifest.get("description") or "(no description)"

    prompt = TTV_JOURNEY_PROMPT.format(
        project_name=project_name,
        description=description,
        schema=schema_block,
        current_features=current_block,
        growth_opportunities=opps_block,
    )

    parsed, raw = await _generate_and_parse(llm, prompt)
    if parsed is None:
        _dump_raw_response(output_path, raw or "", suffix="ttv.raw.txt")
        raise ValueError("ttv journey: LLM did not return a parsable JSON object")

    try:
        _validate_ttv_spec(parsed)
    except ValueError:
        _dump_raw_response(output_path, raw or "", suffix="ttv.raw.txt")
        raise

    journeys = _ttv_spec_to_subject_journeys(parsed)
    explanation = parsed.get("lifecycleDataExplanation")
    return journeys, explanation if isinstance(explanation, str) else ""


async def _compile_engine_features(
    *,
    llm: LLMClient,
    engine: EngineDocument,
    schema: dict[str, Any],
    manifest: dict[str, Any],
    output_path: Path,
) -> list[dict[str, Any]]:
    """Compile every engine feature into a runtime entry. Returns the
    enriched ``compiled_features`` list (possibly empty).
    """
    if not engine.features:
        return []

    schema_block = _schema_for_prompt(schema)
    subjects_block = json.dumps(_subjects_for_prompt(engine), indent=2)
    project_name = manifest.get("project_name") or "unknown"
    description = manifest.get("description") or "(no description)"

    raw_features: list[dict[str, Any]] = []
    failed: list[str] = []
    total = len(engine.features)
    status(f"Compiling {total} engine feature(s) into compiled_features[]")

    for idx, feat in enumerate(engine.features, start=1):
        prompt = FEATURE_PROMPT.format(
            project_name=project_name,
            description=description,
            schema=schema_block,
            subjects=subjects_block,
            feature=json.dumps(_feature_for_prompt(feat), indent=2),
            feature_key=feat.key,
            feature_name=feat.name,
        )
        status(f"  [{idx}/{total}] feature {feat.key}")
        parsed, raw = await _generate_and_parse(llm, prompt)
        if parsed is None:
            _dump_raw_response(output_path, raw or "", suffix=f"feature.{feat.key}.raw.txt")
            failed.append(feat.key)
            continue
        parsed.setdefault("loop_key", feat.key)
        raw_features.append(parsed)

    if failed:
        warning(f"user-journey: dropped {len(failed)} feature(s) that failed to parse: {', '.join(failed)}")
    return _enrich_compiled_features(raw_features, engine)


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
    Compile ``user-journey.yaml`` from schema + growth manifest, optionally
    enriched by engine.yaml.

    The ``ttv_journey_by_subject`` block is built from the schema and the
    growth manifest's growth opportunities via a single LLM call (per the
    TTV spec). The ``compiled_features`` block is built from ``engine.yaml``
    when it has features; otherwise it is empty.

    On LLM failure or invalid response, the previous ``user-journey.yaml``
    is preserved (the function raises so the caller can record the failure).
    """
    state = JourneyState()
    state.schema = _load_yaml(schema_path)
    state.manifest = _load_json(manifest_path)
    state.engine = load_engine_document(engine_path, project_root=project_root)
    state.definitions = build_definitions(state.engine)

    status(
        "Compiling user-journey.yaml: TTV journey from schema + growth opportunities"
        + (f" (+ {len(state.engine.features)} engine feature(s))" if state.engine.features else "")
    )

    journeys, lifecycle_explanation = await _build_ttv_journey_by_subject(
        llm=llm,
        schema=state.schema,
        manifest=state.manifest,
        output_path=output_path,
    )

    state.compiled_features = await _compile_engine_features(
        llm=llm,
        engine=state.engine,
        schema=state.schema,
        manifest=state.manifest,
        output_path=output_path,
    )

    schema_analysis: dict[str, Any] = {
        "analysis_id": str(uuid.uuid4()),
        "updated_at": _utc_now_iso(),
        "lifecycle_stages": [dict(s) for s in LIFECYCLE_STAGES],
        "ttv_journey_by_subject": journeys,
    }
    if lifecycle_explanation:
        schema_analysis["lifecycle_data_explanation"] = lifecycle_explanation
    state.schema_analysis = schema_analysis

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
