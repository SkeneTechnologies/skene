"""
Push utilities for building Supabase migrations from growth loop telemetry.

Builds migration files that create:
- Base schema (event_log, failed_events, enrichment_map) via init
- Allowlisted triggers that INSERT into event_log (Shadow Mirror)
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

from skene.growth_loops.schema_sql import BASE_SCHEMA_SQL, notify_event_log_sql

console = Console()

BASE_SCHEMA_MIGRATION_PREFIX = "20260201000000"
BASE_SCHEMA_MIGRATION_NAME = "skene_growth_schema"


def _trigger_name(table: str, operation: str, loop_id: str) -> str:
    """Generate a safe trigger name."""
    safe_loop = re.sub(r"[^a-z0-9_]", "_", loop_id.lower())
    return f"skene_growth_trg_{table}_{operation}_{safe_loop}"


def _function_name(table: str, operation: str, loop_id: str) -> str:
    """Generate a safe function name for the trigger."""
    safe_loop = re.sub(r"[^a-z0-9_]", "_", loop_id.lower())
    return f"skene_growth_fn_{table}_{operation}_{safe_loop}"


def _build_trigger_function_sql(
    *,
    loop_id: str,
    action_name: str,
    table: str,
    operation: str,
    properties: list[str],
) -> str:
    """
    Build SQL for the trigger function that INSERTs into event_log.

    Shadow Mirror: events land in event_log first. Processor (Phase 3) reads
    from there, enriches, evaluates condition_config, then calls edge function
    proxy which forwards to centralized cloud API.
    """
    fn_name = _function_name(table, operation, loop_id)
    row_var = "NEW" if operation in ("INSERT", "UPDATE") else "OLD"

    props_exprs = []
    for p in properties:
        safe_key = p.replace("'", "''")
        safe_col = p.replace('"', '""')
        props_exprs.append(f"'{safe_key}', {row_var}.\"{safe_col}\"")
    metadata_json = "jsonb_build_object(" + ", ".join(props_exprs) + ")"
    event_type_val = f"{table.lower()}.{operation.lower()}"

    id_col = next((c for c in properties if c.lower() == "id"), properties[0] if properties else None)
    entity_id_expr = f'{row_var}."{id_col}"' if id_col else "NULL"

    body = f"""
BEGIN
  INSERT INTO skene_growth.event_log (entity_id, event_type, metadata)
  VALUES ({entity_id_expr}::uuid, '{event_type_val}', {metadata_json});
EXCEPTION WHEN invalid_text_representation OR OTHERS THEN
  INSERT INTO skene_growth.event_log (entity_id, event_type, metadata)
  VALUES (NULL, '{event_type_val}', {metadata_json});
END;
RETURN NULL;
"""
    return f"""
CREATE OR REPLACE FUNCTION {fn_name}()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, skene_growth
AS $$
BEGIN
{body}
$$;
""".strip()


def _build_trigger_sql(table: str, operation: str, loop_id: str) -> str:
    """Build DROP + CREATE TRIGGER SQL (idempotent)."""
    trg_name = _trigger_name(table, operation, loop_id)
    fn_name = _function_name(table, operation, loop_id)

    timing = "AFTER"
    return f"""
DROP TRIGGER IF EXISTS {trg_name} ON public.{table};
CREATE TRIGGER {trg_name}
  {timing} {operation} ON public.{table}
  FOR EACH ROW
  EXECUTE FUNCTION {fn_name}();
"""


def ensure_base_schema_migration(output_dir: Path) -> Path:
    """Check, build and update the skene_growth_schema migration. Overwrites if exists."""
    migrations_dir = output_dir / "supabase" / "migrations"
    migrations_dir.mkdir(parents=True, exist_ok=True)
    canonical_name = f"{BASE_SCHEMA_MIGRATION_PREFIX}_{BASE_SCHEMA_MIGRATION_NAME}.sql"
    existing = list(migrations_dir.glob(f"*{BASE_SCHEMA_MIGRATION_NAME}*.sql"))
    path = (
        next((p for p in existing if p.name == canonical_name), existing[0])
        if existing
        else migrations_dir / canonical_name
    )
    path.write_text(BASE_SCHEMA_SQL, encoding="utf-8")
    return path


def extract_supabase_telemetry(loop_def: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract telemetry items with type 'supabase' from a loop definition.
    """
    telemetry = loop_def.get("requirements", {}).get("telemetry", [])
    return [t for t in telemetry if isinstance(t, dict) and t.get("type") == "supabase"]


def build_migration_sql(
    loops: list[dict[str, Any]],
    *,
    supabase_url_placeholder: str = "https://YOUR_PROJECT.supabase.co",
    forward_url: str | None = None,
    proxy_secret: str = "YOUR_PROXY_SECRET",
) -> str:
    """
    Build a complete Supabase migration SQL from growth loop definitions.

    Creates:
    - One trigger function + trigger per telemetry item (table, operation)
      that INSERT into skene_growth.event_log (Shadow Mirror)
    - Optionally notify_event_log override when forward_url is provided

    Depends on base schema (event_log, failed_events, enrichment_map, pg_net)
    from skene init / ensure_base_schema_migration. Idempotent: DROP TRIGGER
    IF EXISTS before CREATE.
    """
    seen: set[tuple[str, str, str]] = set()
    fn_parts: list[str] = []
    trg_parts: list[str] = []

    for loop_def in loops:
        loop_id = loop_def.get("loop_id", "growth_loop")
        for t in extract_supabase_telemetry(loop_def):
            table = t.get("table")
            operation = (t.get("operation") or "INSERT").upper()
            action_name = t.get("action_name", "action")
            properties = t.get("properties") or ["id"]

            if not table:
                continue
            key = (table, operation, loop_id)
            if key in seen:
                continue
            seen.add(key)

            fn_sql = _build_trigger_function_sql(
                loop_id=loop_id,
                action_name=action_name,
                table=table,
                operation=operation,
                properties=properties,
            )

            fn_parts.append(fn_sql)

            trg_sql = _build_trigger_sql(table, operation, loop_id)
            trg_parts.append(trg_sql)

    migration = f"""-- Skene Growth: allowlisted triggers insert into event_log (Shadow Mirror)
-- Generated at {datetime.now().isoformat()}
-- Depends on: 20260201000000_skene_growth_schema.sql (run skene init first)

-- Trigger functions
"""
    migration += "\n\n".join(fn_parts)
    migration += "\n\n-- Triggers\n"
    migration += "\n".join(trg_parts)

    if forward_url:
        migration += "\n\n" + notify_event_log_sql(forward_url, proxy_secret)

    return migration.strip()


def write_migration(
    migration_sql: str,
    output_dir: Path,
    *,
    migration_name: str = "skene_telemetry",
) -> Path:
    """Write migration SQL to supabase/migrations/ with timestamp filename."""
    migrations_dir = output_dir / "supabase" / "migrations"
    migrations_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{timestamp}_{migration_name}.sql"
    path = migrations_dir / filename
    path.write_text(migration_sql, encoding="utf-8")
    return path


def _trigger_events_from_loops(loops: list[dict[str, Any]]) -> list[str]:
    """Extract trigger events (table.operation) from loop telemetry."""
    events: list[str] = []
    for loop_def in loops:
        for t in extract_supabase_telemetry(loop_def):
            table = t.get("table")
            op = (t.get("operation") or "INSERT").lower()
            if table:
                events.append(f"{table.lower()}.{op}")
    return list(dict.fromkeys(events))


def push_to_upstream(
    project_root: Path,
    upstream_url: str,
    token: str,
    loops: list[dict[str, Any]],
    context: Path | None = None,
) -> dict[str, Any] | None:
    """
    Push package (growth loops + telemetry.sql) to upstream.
    Returns response dict on success, None on failure.
    """
    from skene.growth_loops.upstream import push_to_upstream

    loops_dir = (context / "growth-loops") if context else None
    trigger_events = _trigger_events_from_loops(loops)
    return push_to_upstream(
        project_root=project_root,
        upstream_url=upstream_url,
        token=token,
        trigger_events=trigger_events,
        loops_count=len(loops),
        loops_dir=loops_dir,
    )


def build_loops_to_supabase(
    loops: list[dict[str, Any]],
    output_dir: Path,
    *,
    supabase_url_placeholder: str = "https://YOUR_PROJECT.supabase.co",
    forward_url: str | None = None,
    proxy_secret: str = "YOUR_PROXY_SECRET",
) -> Path:
    """
    Build migration for the given growth loops.

    Assumes base schema migration exists (call ensure_base_schema_migration first).
    When forward_url is provided (e.g. from --local URL),
    appends notify_event_log override with that upstream ingest URL. Returns migration_path.
    """
    migration_sql = build_migration_sql(
        loops,
        supabase_url_placeholder=supabase_url_placeholder,
        forward_url=forward_url,
        proxy_secret=proxy_secret,
    )
    return write_migration(migration_sql, output_dir)
