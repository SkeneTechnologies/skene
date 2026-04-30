"""
Growth manifest analyzer (schema-driven, with a codebase-only fallback).

Reads the introspected schema produced by :mod:`skene.analyzers.schema_journey`
and uses it as the authoritative driver for discovering *current* growth-relevant
features in the codebase. When the schema has no tables (e.g. the journey
analyzer could not discover any), the analyzer falls back to a codebase-only
inference path that derives features from documentation and source-level
evidence alone.

Pipeline (schema-driven):
1. Load schema YAML (tables, columns, relationships, source_files).
2. LLM hypothesises growth features grounded on schema anchors (no code yet).
3. Targeted ripgrep in the codebase using terms derived from the schema.
4. LLM grounds each hypothesis into a ``GrowthFeature`` with real
   confidence from the snippets.
5. Light prime over README/package manifests fills ``tech_stack`` and
   ``industry``; a final LLM pass adds ``revenue_leakage`` and
   ``growth_opportunities``.
6. Write the resulting manifest JSON.

Pipeline (schemaless fallback, when the schema has no tables):
1. Prime README/package manifests + grep the codebase for a curated set of
   growth-related keywords (invite, billing, onboarding, …).
2. LLM infers ``current_growth_features`` from those snippets only.
3. Same enrichment pass as the schema-driven flow.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from skene.analyzers._journey_common import (
    DEFAULT_EXCLUDES,
    discover_files_by_globs,
    grep_for_keyword,
    join_blocks,
    parse_json,
    read_file_snippet,
)
from skene.llm import LLMClient
from skene.output import status, warning

PRIME_GLOBS: list[str] = [
    "package.json",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
    "Gemfile",
    "requirements.txt",
    "README.md",
    "README",
    "readme.md",
]

PRIME_MAX_FILES = 10
PRIME_MAX_CHARS_PER_FILE = 8_000

MAX_HYPOTHESES = 5
MAX_TERMS_PER_HYPOTHESIS = 5
MAX_SNIPPET_CHARS = 6_000

# Curated keywords used by the schemaless fallback to surface growth-related
# code regions. Kept short so total grep work stays bounded.
SCHEMALESS_GROWTH_KEYWORDS: list[str] = [
    "invite",
    "invitation",
    "referral",
    "subscription",
    "billing",
    "stripe",
    "checkout",
    "webhook",
    "oauth",
    "session",
    "onboarding",
    "notification",
    "analytics",
    "trial",
    "upgrade",
]
SCHEMALESS_MAX_MATCHES_PER_TERM = 6
SCHEMALESS_MAX_FEATURES = 8
SCHEMALESS_MAX_SNIPPET_CHARS = 18_000


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

HYPOTHESIS_PROMPT = """\
You are reading the data schema of a product and must decide which *growth-related*
product surfaces the schema supports.

Schema (YAML — authoritative):
```yaml
{schema}
```

For each plausible growth area that is clearly supported by tables, columns, or
relationships, emit one hypothesis. Consider (but do not invent):
- Referrals / invitations (invite/referrer/referral tables, codes, tokens)
- Subscriptions / billing / pricing tiers
- Usage metering / quotas / limits
- Multi-tenant orgs / teams / memberships (junction tables)
- Notifications / email / digests / webhooks
- Onboarding state (status columns, completed_at, checklist tables)
- Analytics events / funnels (events, sessions, page_views)
- Auth / sessions / OAuth / API keys

Return ONLY a JSON object of this exact shape:
{{
  "hypotheses": [
    {{
      "feature_name": "Team Invitations",
      "detected_intent": "Viral growth via invite links",
      "priority": "high",
      "schema_evidence": ["public.invites.inviter_id -> public.users.id"],
      "search_terms": ["invites", "inviter_id", "Invite", "invite_token"]
    }}
  ]
}}

Hard rules:
- Every hypothesis MUST cite at least one schema anchor in "schema_evidence".
- "search_terms" MUST be 1-{max_terms} literal tokens taken from the schema
  (table names, column names, obvious camelCase variants). Do NOT invent tokens.
- "priority" is one of "high", "medium", "low".
- Emit at most {max_hypotheses} hypotheses — the most impactful ones.
- Return ONLY the JSON object. No prose, no code fences.
"""


GROUND_PROMPT = """\
You are grounding a schema-based growth hypothesis in real code.

Schema excerpt (YAML):
```yaml
{schema_excerpt}
```

Hypothesis:
```json
{hypothesis}
```

Code snippets (ripgrep results, file:line prefixes preserved):
```
{snippets}
```

If the snippets confirm the hypothesis, emit one or more GrowthFeature objects.
If the snippets do NOT support it, emit an empty list.

Return ONLY a JSON object of this exact shape:
{{
  "features": [
    {{
      "feature_name": "Team Invitations",
      "detected_intent": "Viral growth via invite links",
      "confidence_score": 0.82,
      "growth_potential": ["Add invite rewards", "Track invite acceptance rate"]
    }}
  ]
}}

Rules:
- "confidence_score" is a float in [0.0, 1.0] reflecting how strongly the snippets confirm the hypothesis.
- Do NOT include file_path, entry_point, or growth_pillars. They are intentionally omitted.
- Do NOT invent features the snippets do not support.
- Return ONLY the JSON object. No prose, no code fences.
"""


SCHEMALESS_FEATURES_PROMPT = """\
You are inferring the *current* growth-related features of a product purely
from its codebase (no database schema is available).

Project files (READMEs, package manifests, growth-keyword code snippets):
```
{snippets}
```

Identify the growth-relevant capabilities the product already ships
(invitations, sharing, billing/monetisation, onboarding, notifications,
analytics/events, auth, multi-tenant orgs, etc.). Be conservative — only emit
a feature when the snippets clearly support it.

Return ONLY a JSON object of this exact shape:
{{
  "features": [
    {{
      "feature_name": "Team Invitations",
      "detected_intent": "Viral growth via invite links",
      "confidence_score": 0.7,
      "growth_potential": ["Add invite rewards", "Track invite acceptance rate"]
    }}
  ]
}}

Rules:
- "confidence_score" is a float in [0.0, 1.0] reflecting evidence strength.
- Do NOT include file_path, entry_point, or growth_pillars.
- Emit at most {max_features} features — the most clearly supported ones.
- Return ONLY the JSON object. No prose, no code fences.
"""


ENRICH_PROMPT = """\
You are completing a growth manifest. The "current_growth_features" were already
derived from the data schema plus grounded code evidence. Your job is to fill in
the remaining manifest fields using the documentation/config files below.

Project files (package manifests, README, docs):
```
{docs}
```

Current growth features already identified:
```json
{features}
```

Schema summary (table names only):
{table_names}

Return ONLY a JSON object of this exact shape:
{{
  "project_name": "string",
  "description": "string or null",
  "tech_stack": {{
    "framework": "string or null",
    "language": "string",
    "database": "string or null",
    "auth": "string or null",
    "deployment": "string or null",
    "package_manager": "string or null",
    "services": ["string"]
  }},
  "industry": {{
    "primary": "string or null",
    "secondary": ["string"],
    "confidence": 0.0,
    "evidence": ["string"]
  }},
  "revenue_leakage": [
    {{"issue": "string", "file_path": "string or null", "impact": "high|medium|low", "recommendation": "string"}}
  ],
  "growth_opportunities": [
    {{"feature_name": "string", "description": "string", "priority": "high|medium|low"}}
  ]
}}

Rules:
- "tech_stack.language" is REQUIRED — infer it from file extensions or package manifests.
- Growth opportunities MUST complement (not duplicate) the existing features above.
- Base revenue_leakage on signals from the provided files; omit if none.
- Return ONLY the JSON object. No prose, no code fences.
"""


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class GrowthState:
    """Accumulated state across the schema-driven growth pipeline."""

    schema: dict[str, Any] = field(default_factory=dict)
    hypotheses: list[dict[str, Any]] = field(default_factory=list)
    features: list[dict[str, Any]] = field(default_factory=list)
    tech_stack: dict[str, Any] = field(default_factory=lambda: {"language": "Unknown"})
    industry: dict[str, Any] | None = None
    revenue_leakage: list[dict[str, Any]] = field(default_factory=list)
    growth_opportunities: list[dict[str, Any]] = field(default_factory=list)
    project_name: str = ""
    description: str | None = None

    def to_manifest_dict(self) -> dict[str, Any]:
        """Return the growth-manifest.json payload as a plain dict.

        The schema-driven flow omits ``file_path``, ``entry_point``, and
        ``growth_pillars`` on features; all three are now optional on the
        canonical :class:`skene.manifest.schema.GrowthManifest` model, so this
        payload validates against it.
        """
        return {
            "version": "1.0",
            "project_name": self.project_name or "unknown",
            "description": self.description,
            "tech_stack": self.tech_stack,
            "industry": self.industry,
            "current_growth_features": self.features,
            "growth_opportunities": self.growth_opportunities,
            "revenue_leakage": self.revenue_leakage,
        }


# ---------------------------------------------------------------------------
# Schema loading
# ---------------------------------------------------------------------------


def load_schema(schema_path: Path) -> dict[str, Any]:
    """Load and lightly normalise the schema YAML produced by analyse-journey."""
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    with open(schema_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        raise ValueError(f"Schema file is not a mapping: {schema_path}")

    tables = data.get("tables") or []
    if not isinstance(tables, list):
        tables = []

    normalised_tables: list[dict[str, Any]] = []
    for t in tables:
        if not isinstance(t, dict) or not t.get("name"):
            continue
        normalised_tables.append(
            {
                "name": t["name"],
                "description": t.get("description") or "",
                "columns": t.get("columns") or [],
                "relationships": t.get("relationships") or [],
                "source_files": t.get("source_files") or [],
            }
        )

    return {"tables": normalised_tables, "notes": data.get("notes") or []}


def _schema_for_prompt(schema: dict[str, Any], max_chars: int = 12_000) -> str:
    """Render the schema as compact YAML for inclusion in prompts."""
    compact = {
        "tables": [
            {
                "name": t["name"],
                "description": t.get("description") or None,
                "columns": [
                    {
                        "name": c.get("name"),
                        "type": c.get("type"),
                        "primary_key": c.get("primary_key", False),
                    }
                    for c in t.get("columns", [])
                    if isinstance(c, dict) and c.get("name")
                ],
                "relationships": t.get("relationships") or [],
            }
            for t in schema.get("tables", [])
        ]
    }
    rendered = yaml.safe_dump(compact, sort_keys=False, default_flow_style=False)
    if len(rendered) > max_chars:
        rendered = rendered[:max_chars] + "\n# [truncated]"
    return rendered


# ---------------------------------------------------------------------------
# Phase 2: schema -> hypotheses
# ---------------------------------------------------------------------------


async def _infer_hypotheses(llm: LLMClient, state: GrowthState) -> None:
    if not state.schema.get("tables"):
        warning("Schema has no tables — nothing to infer growth features from")
        return

    prompt = HYPOTHESIS_PROMPT.format(
        schema=_schema_for_prompt(state.schema),
        max_terms=MAX_TERMS_PER_HYPOTHESIS,
        max_hypotheses=MAX_HYPOTHESES,
    )

    try:
        response = await llm.generate_content(prompt)
    except Exception as e:
        warning(f"Hypothesis LLM call failed: {e}")
        return

    parsed = parse_json(response)
    if parsed is None:
        warning("Could not parse hypothesis response")
        return

    hypotheses = parsed.get("hypotheses")
    if not isinstance(hypotheses, list):
        warning("Hypothesis response missing 'hypotheses' list")
        return

    valid: list[dict[str, Any]] = []
    for h in hypotheses[:MAX_HYPOTHESES]:
        if not isinstance(h, dict):
            continue
        name = (h.get("feature_name") or "").strip()
        terms = [t for t in (h.get("search_terms") or []) if isinstance(t, str) and t.strip()]
        evidence = [e for e in (h.get("schema_evidence") or []) if isinstance(e, str) and e.strip()]
        if not name or not terms or not evidence:
            continue
        priority = h.get("priority") if h.get("priority") in ("high", "medium", "low") else "medium"
        valid.append(
            {
                "feature_name": name,
                "detected_intent": (h.get("detected_intent") or "").strip(),
                "priority": priority,
                "schema_evidence": evidence,
                "search_terms": terms[:MAX_TERMS_PER_HYPOTHESIS],
            }
        )

    state.hypotheses = valid
    status(f"Hypotheses: {len(valid)} growth feature candidate(s) from schema")


# ---------------------------------------------------------------------------
# Phase 3: grep evidence
# ---------------------------------------------------------------------------


def _gather_evidence(
    hypothesis: dict[str, Any],
    path: Path,
    excludes: list[str],
    max_matches_per_term: int = 20,
) -> list[str]:
    """Run ripgrep for each search term and collect deduplicated snippet blocks."""
    seen: set[str] = set()
    blocks: list[str] = []
    for term in hypothesis["search_terms"]:
        matches = grep_for_keyword(
            term,
            path,
            excludes=excludes,
            max_matches=max_matches_per_term,
            context_lines=2,
        )
        for m in matches:
            if m not in seen:
                seen.add(m)
                blocks.append(m)
    return blocks


def _schema_excerpt_for_hypothesis(hypothesis: dict[str, Any], schema: dict[str, Any], max_chars: int = 2_500) -> str:
    """Pull the small slice of schema that this hypothesis references."""
    referenced: set[str] = set()
    for ev in hypothesis.get("schema_evidence", []):
        for part in ev.replace("->", " ").split():
            token = part.strip(".,;:()").lower()
            if "." in token:
                schema_part, _, table_part = token.partition(".")
                referenced.add(f"{schema_part}.{table_part.split('.')[0]}")

    tables = schema.get("tables", [])
    picked: list[dict[str, Any]] = []
    for t in tables:
        tname = str(t.get("name", "")).lower()
        if tname in referenced or any(tname == r.split(".")[1] for r in referenced if "." in r):
            picked.append(t)
    if not picked:
        picked = tables[:4]

    rendered = yaml.safe_dump({"tables": picked}, sort_keys=False, default_flow_style=False)
    if len(rendered) > max_chars:
        rendered = rendered[:max_chars] + "\n# [truncated]"
    return rendered


async def _ground_hypotheses(
    llm: LLMClient,
    path: Path,
    state: GrowthState,
    excludes: list[str],
) -> None:
    if not state.hypotheses:
        return

    total = len(state.hypotheses)
    for i, hyp in enumerate(state.hypotheses, start=1):
        blocks = await asyncio.to_thread(_gather_evidence, hyp, path, excludes)
        if not blocks:
            status(f"[{i}/{total}] {hyp['feature_name']!r}: no code evidence, skipping")
            continue

        status(f"[{i}/{total}] {hyp['feature_name']!r}: {len(blocks)} snippet(s), grounding")

        prompt = GROUND_PROMPT.format(
            schema_excerpt=_schema_excerpt_for_hypothesis(hyp, state.schema),
            hypothesis=json.dumps(hyp, indent=2),
            snippets=join_blocks(blocks, max_chars=MAX_SNIPPET_CHARS),
        )

        try:
            response = await llm.generate_content(prompt)
        except Exception as e:
            warning(f"Grounding LLM call failed for {hyp['feature_name']!r}: {e}")
            continue

        parsed = parse_json(response)
        if parsed is None:
            warning(f"Could not parse grounding response for {hyp['feature_name']!r}")
            continue

        for feat in parsed.get("features") or []:
            if not isinstance(feat, dict):
                continue
            normalised = _normalise_feature(feat, fallback=hyp)
            if normalised is not None:
                _merge_feature(state, normalised)


def _normalise_feature(feat: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any] | None:
    name = (feat.get("feature_name") or fallback.get("feature_name") or "").strip()
    intent = (feat.get("detected_intent") or fallback.get("detected_intent") or "").strip()
    if not name or not intent:
        return None

    try:
        score = float(feat.get("confidence_score", 0.5))
    except (TypeError, ValueError):
        score = 0.5
    score = max(0.0, min(1.0, score))

    return {
        "feature_name": name,
        "detected_intent": intent,
        "confidence_score": score,
        "growth_potential": [
            s.strip() for s in (feat.get("growth_potential") or []) if isinstance(s, str) and s.strip()
        ],
    }


def _merge_feature(state: GrowthState, feature: dict[str, Any]) -> None:
    key = feature["feature_name"].lower()
    for existing in state.features:
        if existing["feature_name"].lower() == key:
            if feature["confidence_score"] > existing["confidence_score"]:
                existing["confidence_score"] = feature["confidence_score"]
            for g in feature["growth_potential"]:
                if g not in existing["growth_potential"]:
                    existing["growth_potential"].append(g)
            return
    state.features.append(feature)


# ---------------------------------------------------------------------------
# Schemaless fallback: infer features from the codebase alone
# ---------------------------------------------------------------------------


async def _infer_features_from_codebase(
    llm: LLMClient,
    path: Path,
    state: GrowthState,
    excludes: list[str],
) -> None:
    """Populate ``state.features`` from docs + growth-keyword code snippets only.

    Used when the journey analyzer could not discover any database tables.
    """
    doc_files = await asyncio.to_thread(discover_files_by_globs, path, PRIME_GLOBS, excludes, PRIME_MAX_FILES)
    doc_parts = [read_file_snippet(f, path, PRIME_MAX_CHARS_PER_FILE) for f in doc_files]

    seen: set[str] = set()
    code_blocks: list[str] = []
    for term in SCHEMALESS_GROWTH_KEYWORDS:
        matches = await asyncio.to_thread(
            grep_for_keyword,
            term,
            path,
            excludes=excludes,
            max_matches=SCHEMALESS_MAX_MATCHES_PER_TERM,
            context_lines=2,
        )
        for m in matches:
            if m not in seen:
                seen.add(m)
                code_blocks.append(m)

    if not doc_parts and not code_blocks:
        warning(
            "Schemaless feature inference: no documentation or growth-related "
            "code found — leaving current_growth_features empty"
        )
        return

    snippets = "\n\n".join(p for p in doc_parts if p)
    if code_blocks:
        joined_code = join_blocks(code_blocks, max_chars=SCHEMALESS_MAX_SNIPPET_CHARS)
        snippets = (snippets + "\n\n---\n\n" + joined_code).strip() if snippets else joined_code
    if len(snippets) > SCHEMALESS_MAX_SNIPPET_CHARS:
        snippets = snippets[:SCHEMALESS_MAX_SNIPPET_CHARS] + "\n\n...[truncated]"

    status(f"Schemaless feature inference: {len(doc_files)} doc file(s), {len(code_blocks)} growth-keyword snippet(s)")

    prompt = SCHEMALESS_FEATURES_PROMPT.format(
        snippets=snippets,
        max_features=SCHEMALESS_MAX_FEATURES,
    )

    try:
        response = await llm.generate_content(prompt)
    except Exception as e:
        warning(f"Schemaless feature LLM call failed: {e}")
        return

    parsed = parse_json(response)
    if parsed is None:
        warning("Could not parse schemaless feature response")
        return

    fallback = {"feature_name": "", "detected_intent": ""}
    for feat in parsed.get("features") or []:
        if not isinstance(feat, dict):
            continue
        normalised = _normalise_feature(feat, fallback=fallback)
        if normalised is not None:
            _merge_feature(state, normalised)


# ---------------------------------------------------------------------------
# Phase 4: prime docs + enrich manifest
# ---------------------------------------------------------------------------


async def _enrich_manifest(
    llm: LLMClient,
    path: Path,
    state: GrowthState,
    excludes: list[str],
) -> None:
    files = await asyncio.to_thread(discover_files_by_globs, path, PRIME_GLOBS, excludes, PRIME_MAX_FILES)
    if not files:
        status("Enrichment: no README / package manifest files found")
        docs = ""
    else:
        parts = [read_file_snippet(f, path, PRIME_MAX_CHARS_PER_FILE) for f in files]
        docs = "\n\n".join(p for p in parts if p)
        status(f"Enrichment: reading {len(files)} doc/config file(s)")

    table_names = ", ".join(t["name"] for t in state.schema.get("tables", [])[:50]) or "(none)"

    prompt = ENRICH_PROMPT.format(
        docs=docs or "(no documentation files found)",
        features=json.dumps(state.features, indent=2) if state.features else "[]",
        table_names=table_names,
    )

    try:
        response = await llm.generate_content(prompt)
    except Exception as e:
        warning(f"Enrichment LLM call failed: {e}")
        return

    parsed = parse_json(response)
    if parsed is None:
        warning("Could not parse enrichment response")
        return

    if name := parsed.get("project_name"):
        if isinstance(name, str) and name.strip():
            state.project_name = name.strip()

    if desc := parsed.get("description"):
        if isinstance(desc, str) and desc.strip():
            state.description = desc.strip()

    tech = parsed.get("tech_stack")
    if isinstance(tech, dict) and tech.get("language"):
        state.tech_stack = {
            "framework": tech.get("framework"),
            "language": tech["language"],
            "database": tech.get("database"),
            "auth": tech.get("auth"),
            "deployment": tech.get("deployment"),
            "package_manager": tech.get("package_manager"),
            "services": [s for s in (tech.get("services") or []) if isinstance(s, str)],
        }

    industry = parsed.get("industry")
    if isinstance(industry, dict):
        state.industry = {
            "primary": industry.get("primary"),
            "secondary": [s for s in (industry.get("secondary") or []) if isinstance(s, str)],
            "confidence": industry.get("confidence"),
            "evidence": [s for s in (industry.get("evidence") or []) if isinstance(s, str)],
        }

    for item in parsed.get("revenue_leakage") or []:
        if not isinstance(item, dict):
            continue
        issue = (item.get("issue") or "").strip()
        impact = item.get("impact")
        recommendation = (item.get("recommendation") or "").strip()
        if not issue or impact not in ("high", "medium", "low") or not recommendation:
            continue
        state.revenue_leakage.append(
            {
                "issue": issue,
                "file_path": item.get("file_path") or None,
                "impact": impact,
                "recommendation": recommendation,
            }
        )

    existing_names = {f["feature_name"].lower() for f in state.features}
    for opp in parsed.get("growth_opportunities") or []:
        if not isinstance(opp, dict):
            continue
        name = (opp.get("feature_name") or "").strip()
        description = (opp.get("description") or "").strip()
        priority = opp.get("priority")
        if not name or not description or priority not in ("high", "medium", "low"):
            continue
        if name.lower() in existing_names:
            continue
        state.growth_opportunities.append(
            {
                "feature_name": name,
                "description": description,
                "priority": priority,
            }
        )


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def write_growth_manifest(path: Path, manifest: dict[str, Any]) -> None:
    """Serialise the growth-manifest payload as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(manifest)
    payload.setdefault("generated_at", datetime.now().isoformat())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------


async def analyse_growth_from_schema(
    *,
    path: Path,
    schema_path: Path,
    llm: LLMClient,
    output_path: Path,
    excludes: list[str] | None = None,
) -> GrowthState:
    """Derive a growth manifest from an existing schema + codebase evidence.

    Writes ``output_path`` as JSON even on partial failure.
    """
    excludes = list(excludes) if excludes else list(DEFAULT_EXCLUDES)
    state = GrowthState()

    try:
        state.schema = load_schema(schema_path)
        status(f"Loaded schema: {len(state.schema.get('tables', []))} table(s)")

        if state.schema.get("tables"):
            await _infer_hypotheses(llm, state)
            await _ground_hypotheses(llm, path, state, excludes)
        else:
            status("No schema tables — falling back to codebase-only feature inference")
            await _infer_features_from_codebase(llm, path, state, excludes)

        await _enrich_manifest(llm, path, state, excludes)

        write_growth_manifest(output_path, state.to_manifest_dict())
    except Exception:
        write_growth_manifest(output_path, state.to_manifest_dict())
        raise

    return state
