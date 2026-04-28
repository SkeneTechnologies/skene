"""
Engine planner.

Reads a ``growth-manifest.json`` (produced by ``analyse-growth-from-schema``)
and a ``schema.yaml`` (produced by ``analyse-journey``), then asks the LLM to
promote three concrete growth features — grounded in the manifest's
``growth_opportunities`` and the introspected schema — into a fresh
``new-features.yaml`` proposal sidecar.

The existing ``engine.yaml`` is read for prompt context only (so the LLM does
not duplicate features already shipped) and is never modified by this stage.
Each run rewrites ``new-features.yaml`` from scratch with that run's planned
features.

When the schema has no tables (e.g. the journey analyzer could not discover
any), a schemaless prompt is used instead: subjects use synthetic ``app.<key>``
tables and features use a non-DB ``app.<key>.virtual`` source with no
``action`` (since database triggers cannot be wired without real tables).

Pipeline:
1. Load growth manifest + schema.
2. Pick the top three growth opportunities (rank by priority) as seeds.
3. Ask the LLM to emit an engine delta (subjects + features) that implements
   those opportunities — against the real schema, or schemalessly when no
   schema tables are available.
4. Write ``new-features.yaml`` (default: beside ``engine.yaml``) with a JSON
   array of the features from this planning run only. Use
   ``new_features_path`` to place it in another directory (e.g. the legacy
   skene-context bundle).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from skene.analyzers._journey_common import (
    is_skene_growth_table,
    relationship_targets_skene_growth,
    source_targets_skene_growth,
)
from skene.engine.storage import (
    EngineDocument,
    load_engine_document,
    parse_engine_delta_response,
    write_new_features_sidecar,
)
from skene.llm import LLMClient
from skene.output import status, warning

DEFAULT_FEATURE_COUNT = 3

_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _drop_skene_growth_entries(delta: EngineDocument) -> EngineDocument:
    """Strip any subjects/features that reference Skene-managed tables."""
    subjects = [s for s in delta.subjects if not is_skene_growth_table(s.table)]
    features = [f for f in delta.features if not source_targets_skene_growth(f.source)]
    return EngineDocument(version=delta.version, subjects=subjects, features=features)


def _strip_actions(delta: EngineDocument) -> EngineDocument:
    """Drop ``action`` from every feature (used in the schemaless plan flow).

    Schemaless features have no real DB source and cannot be wired to database
    triggers — keeping ``action`` would silently produce invalid runtime wiring.
    """
    cleaned_features = [f.model_copy(update={"action": None}) for f in delta.features]
    return EngineDocument(
        version=delta.version,
        subjects=delta.subjects,
        features=cleaned_features,
    )


def _filter_skene_growth_from_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``schema`` with any ``skene_growth*`` tables stripped."""
    tables = schema.get("tables") or []
    kept: list[dict[str, Any]] = []
    for t in tables:
        if not isinstance(t, dict):
            continue
        if is_skene_growth_table((t.get("name") or "").strip()):
            continue
        clean = dict(t)
        clean["relationships"] = [
            rel
            for rel in (clean.get("relationships") or [])
            if isinstance(rel, dict) and not relationship_targets_skene_growth(rel)
        ]
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


SCHEMALESS_PLAN_PROMPT = """\
You are a growth engineering planner. Your job is to turn growth opportunities
into concrete features in the product's ``skene/engine.yaml``.

NOTE: No database schema was discovered for this product. Plan features purely
from product/business context. Do NOT invent database tables or columns; the
features cannot be wired to database triggers.

Project: {project_name}
Description: {description}

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
    {{"key": "user", "table": "app.user", "kind": "actor"}}
  ],
  "features": [
    {{
      "key": "snake_case_key",
      "name": "Human Readable Name",
      "source": "app.snake_case_key.virtual",
      "how_it_works": "1-3 sentence explanation of runtime behaviour",
      "match_intent": "short hint describing what triggers this feature",
      "subject_state_analysis": {{
        "lifecycle_subject": "<subject.key referenced above>",
        "subject_id_path": "id",
        "action_target_path": null,
        "state": null,
        "record_predicates": [],
        "analysis_notes": "freeform notes; no schema is available"
      }}
    }}
  ]
}}

Hard rules:
- Emit EXACTLY {feature_count} features, one per selected opportunity, in the same order.
- Subject ``table`` MUST start with ``app.`` (synthetic identifier; no real DB).
- Feature ``source`` MUST be ``app.<feature_key>.virtual`` matching the feature's own ``key``.
- Do NOT include an ``action`` field. Schemaless features cannot be wired to
  database triggers and must remain client-side / informational.
- Include every subject referenced by ``lifecycle_subject`` in ``subjects``.
  Reuse keys already listed in the existing engine when applicable.
- Feature keys must be stable ``snake_case`` identifiers unique to engine.yaml.
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


def _select_opportunities(manifest: dict[str, Any], count: int) -> list[dict[str, Any]]:
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
    new_features_path: Path | None = None,
    project_root: Path | None = None,
    feature_count: int = DEFAULT_FEATURE_COUNT,
) -> PlanState:
    """
    Promote top growth opportunities into a fresh ``new-features.yaml`` proposal.

    The existing ``engine.yaml`` is read for LLM context only and is never
    modified by this stage. On a successful LLM parse, ``new-features.yaml``
    is rewritten from scratch (beside ``engine_path`` or at
    ``new_features_path``) with this run's planned features.
    """
    state = PlanState()
    state.manifest = _load_manifest(manifest_path)
    state.schema = _filter_skene_growth_from_schema(_load_schema(schema_path))
    state.existing_engine = load_engine_document(engine_path, project_root=project_root)

    state.selected_opportunities = _select_opportunities(state.manifest, feature_count)
    if not state.selected_opportunities:
        warning("No growth_opportunities found in manifest — nothing to plan.")
        return state

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

    schemaless = not (state.schema.get("tables") or [])
    status(
        f"Planning {len(state.selected_opportunities)} engine feature(s) from growth opportunities"
        + (" (schemaless mode)" if schemaless else "")
    )

    if schemaless:
        prompt = SCHEMALESS_PLAN_PROMPT.format(
            project_name=state.manifest.get("project_name") or "unknown",
            description=state.manifest.get("description") or "(no description)",
            engine_context=engine_context,
            current_features=json.dumps(current_features, indent=2),
            opportunities=json.dumps(state.selected_opportunities, indent=2),
            feature_count=feature_count,
        )
    else:
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
        return state

    try:
        state.delta = parse_engine_delta_response(response or "")
    except Exception as e:
        warning(f"Could not parse engine delta response: {e}")
        return state

    state.delta = _drop_skene_growth_entries(state.delta)
    if schemaless:
        state.delta = _strip_actions(state.delta)

    write_new_features_sidecar(
        engine_path,
        state.delta.features,
        project_root=project_root,
        output_path=new_features_path,
    )

    new_feature_keys = [f.key for f in state.delta.features]
    status(f"Wrote new-features.yaml with {len(new_feature_keys)} feature(s) ({', '.join(new_feature_keys) or 'none'})")

    return state
