"""
Engine planner.

Reads a ``growth-manifest.json`` (produced by ``analyse-growth-from-schema``)
and a ``schema.yaml`` (produced by ``analyse-journey``), then asks the LLM to
promote three concrete growth features — grounded in the manifest's
``growth_opportunities`` and the introspected schema — into the
``skene/engine.yaml`` engine document.

Pipeline:
1. Load growth manifest + schema.
2. Pick the top three growth opportunities (rank by priority) as seeds.
3. Ask the LLM to emit an engine delta (subjects + features) that implements
   those opportunities against the real schema.
4. Merge the delta into any existing ``engine.yaml`` by key and persist.
5. Write ``new-features.yaml`` next to ``engine.yaml`` with a JSON array of
   the features from this planning run only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from skene.engine.storage import (
    EngineDocument,
    load_engine_document,
    merge_engine_documents,
    parse_engine_delta_response,
    write_engine_document,
    write_new_features_sidecar,
)
from skene.llm import LLMClient
from skene.output import status, warning

DEFAULT_FEATURE_COUNT = 3

_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _is_skene_growth_table(name: str) -> bool:
    """True when a ``schema.table`` string belongs to Skene's own growth plane."""
    n = (name or "").lower()
    if not n:
        return False
    schema, _, table = n.partition(".")
    if schema == "skene_growth" or schema.startswith("skene_growth_"):
        return True
    return table.startswith("skene_growth")


def _source_targets_skene_growth(source: str) -> bool:
    """True when an engine feature ``source`` (``schema.table.op``) is Skene-managed."""
    parts = (source or "").split(".")
    if len(parts) < 2:
        return False
    return _is_skene_growth_table(".".join(parts[:2]))


def _drop_skene_growth_entries(delta: EngineDocument) -> EngineDocument:
    """Strip any subjects/features that reference Skene-managed tables."""
    subjects = [s for s in delta.subjects if not _is_skene_growth_table(s.table)]
    features = [
        f for f in delta.features if not _source_targets_skene_growth(f.source)
    ]
    return EngineDocument(version=delta.version, subjects=subjects, features=features)


def _filter_skene_growth_from_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``schema`` with any ``skene_growth*`` tables stripped."""
    tables = schema.get("tables") or []
    kept: list[dict[str, Any]] = []
    for t in tables:
        if not isinstance(t, dict):
            continue
        name = (t.get("name") or "").strip()
        if _is_skene_growth_table(name):
            continue
        clean = dict(t)
        rels = []
        for rel in clean.get("relationships") or []:
            if not isinstance(rel, dict):
                continue
            target = rel.get("to")
            if isinstance(target, str):
                parts = target.split(".")
                table_ref = ".".join(parts[:-1]) if len(parts) >= 3 else parts[0]
                if _is_skene_growth_table(table_ref):
                    continue
            rels.append(rel)
        clean["relationships"] = rels
        kept.append(clean)
    return {**schema, "tables": kept}


PLAN_PROMPT = """\
You are a growth engineering planner. Your job is to turn three growth
opportunities into concrete features in the product's ``skene/engine.yaml``.

Project: {project_name}
Description: {description}

Database schema (YAML — authoritative, use real tables/columns):
```yaml
{schema}
```

Existing engine document (for context — do not duplicate features already here):
{engine_context}

Current growth features already shipped in the product:
```json
{current_features}
```

Selected growth opportunities to implement now (pick a concrete shape for each):
```json
{opportunities}
```

Return ONLY a JSON object matching this shape (no prose, no code fences):
{{
  "version": 1,
  "subjects": [
    {{"key": "document", "table": "public.documents", "kind": "actor"}}
  ],
  "features": [
    {{
      "key": "snake_case_key",
      "name": "Human Readable Name",
      "source": "schema.table.insert|update|delete",
      "how_it_works": "1-3 sentence explanation of runtime behaviour",
      "match_intent": "short hint describing which table/columns drive matching",
      "subject_state_analysis": {{
        "lifecycle_subject": "<subject.key referenced above>",
        "subject_id_path": "id",
        "action_target_path": "owner_id",
        "state": null,
        "record_predicates": [],
        "analysis_notes": "freeform notes explaining assumptions and predicates"
      }},
      "action": {{
        "use": "email|webhook|queue",
        "config": {{"...": "..."}}
      }}
    }}
  ]
}}

Hard rules:
- Emit EXACTLY {feature_count} features, one per selected opportunity, in the same order.
- ``source`` MUST be ``<schema>.<table>.<operation>`` using tables that exist
  in the schema above. Operation is ``insert``, ``update`` or ``delete``.
- Include every subject referenced by ``lifecycle_subject`` in ``subjects``.
  Reuse keys already listed in the existing engine when applicable.
- ``action`` is OPTIONAL. Include it only when a database trigger / side-effect
  (email, webhook, queue) is needed; omit it for purely client-side features.
- Feature keys must be stable ``snake_case`` identifiers unique to engine.yaml.
- Ground ``match_intent`` and ``analysis_notes`` in concrete schema columns.
- Do NOT invent tables or columns that are absent from the schema.
- NEVER use ``skene_growth`` schema or any ``skene_growth*`` table in
  ``source`` or ``action`` config — those belong to Skene's own
  instrumentation, not the application being planned.
- Keep ``version`` = 1. Return ONLY the JSON object.
"""


@dataclass
class PlanState:
    """Accumulated state across the engine planning pipeline."""

    manifest: dict[str, Any] = field(default_factory=dict)
    schema: dict[str, Any] = field(default_factory=dict)
    selected_opportunities: list[dict[str, Any]] = field(default_factory=list)
    existing_engine: EngineDocument | None = None
    delta: EngineDocument | None = None
    merged: EngineDocument | None = None


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------


def _load_manifest(manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.exists():
        raise FileNotFoundError(f"Growth manifest not found: {manifest_path}")
    with open(manifest_path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Growth manifest is not a JSON object: {manifest_path}")
    return data


def _load_schema(schema_path: Path) -> dict[str, Any]:
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    with open(schema_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Schema file is not a mapping: {schema_path}")
    return data


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


def _select_opportunities(
    manifest: dict[str, Any], count: int
) -> list[dict[str, Any]]:
    opportunities = manifest.get("growth_opportunities") or []
    if not isinstance(opportunities, list):
        return []

    clean: list[dict[str, Any]] = []
    for opp in opportunities:
        if not isinstance(opp, dict):
            continue
        name = (opp.get("feature_name") or "").strip()
        description = (opp.get("description") or "").strip()
        priority = opp.get("priority") if opp.get("priority") in _PRIORITY_ORDER else "medium"
        if not name or not description:
            continue
        clean.append(
            {
                "feature_name": name,
                "description": description,
                "priority": priority,
            }
        )

    clean.sort(key=lambda o: _PRIORITY_ORDER.get(o["priority"], 1))
    return clean[:count]


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------


async def plan_engine_from_manifest(
    *,
    manifest_path: Path,
    schema_path: Path,
    llm: LLMClient,
    engine_path: Path,
    project_root: Path | None = None,
    feature_count: int = DEFAULT_FEATURE_COUNT,
) -> PlanState:
    """
    Promote top growth opportunities into engine.yaml features via the LLM.

    Writes ``engine_path`` even on partial failure (the existing document is
    preserved if the LLM call fails). On a successful LLM parse and merge,
    also writes ``new-features.yaml`` beside ``engine_path`` (JSON array of
    this run's planned features).
    """
    state = PlanState()
    state.manifest = _load_manifest(manifest_path)
    state.schema = _filter_skene_growth_from_schema(_load_schema(schema_path))

    state.selected_opportunities = _select_opportunities(state.manifest, feature_count)
    if not state.selected_opportunities:
        warning("No growth_opportunities found in manifest — nothing to plan.")
        state.existing_engine = load_engine_document(engine_path, project_root=project_root)
        state.merged = state.existing_engine
        write_engine_document(engine_path, state.merged, project_root=project_root)
        return state

    state.existing_engine = load_engine_document(engine_path, project_root=project_root)

    current_features = state.manifest.get("current_growth_features") or []
    if not isinstance(current_features, list):
        current_features = []

    engine_context = (
        yaml.safe_dump(
            state.existing_engine.model_dump(mode="json"),
            sort_keys=False,
            default_flow_style=False,
        )
        if state.existing_engine.subjects or state.existing_engine.features
        else "(engine.yaml is empty — seed it.)"
    )

    status(
        f"Planning {len(state.selected_opportunities)} engine feature(s) from growth opportunities"
    )

    prompt = PLAN_PROMPT.format(
        project_name=state.manifest.get("project_name") or "unknown",
        description=state.manifest.get("description") or "(no description)",
        schema=_schema_for_prompt(state.schema),
        engine_context=engine_context,
        current_features=json.dumps(current_features, indent=2),
        opportunities=json.dumps(state.selected_opportunities, indent=2),
        feature_count=feature_count,
    )

    try:
        response = await llm.generate_content(prompt)
    except Exception as e:
        warning(f"Engine planning LLM call failed: {e}")
        state.merged = state.existing_engine
        write_engine_document(engine_path, state.merged, project_root=project_root)
        return state

    try:
        state.delta = parse_engine_delta_response(response or "")
    except Exception as e:
        warning(f"Could not parse engine delta response: {e}")
        state.merged = state.existing_engine
        write_engine_document(engine_path, state.merged, project_root=project_root)
        return state

    state.delta = _drop_skene_growth_entries(state.delta)

    state.merged = merge_engine_documents(state.existing_engine, state.delta)
    write_engine_document(engine_path, state.merged, project_root=project_root)
    write_new_features_sidecar(
        engine_path,
        state.delta.features,
        project_root=project_root,
    )

    new_feature_keys = [f.key for f in state.delta.features]
    status(
        f"Updated engine.yaml and new-features.yaml with the feature(s) "
        f"(added/updated: {', '.join(new_feature_keys) or 'none'})"
    )

    return state
