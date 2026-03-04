"""
Deploy utilities for building Supabase migrations from growth loop telemetry.

Builds migration files that create:
- Base schema (event_log, growth_loops, etc.) via init
- Allowlisted triggers that INSERT into event_log (Shadow Mirror)
- Edge function proxy (forwards to centralized cloud API with HMAC signature)

Triggers do not call pg_net. Events land in event_log; the processor (Phase 3)
reads from there, enriches, evaluates condition_config, then calls the edge function
proxy which forwards to the centralized cloud API for execution.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

from skene_growth.growth_loops.processor_sql import PROCESSOR_SQL
from skene_growth.growth_loops.schema_sql import BASE_SCHEMA_SQL

console = Console()

BASE_SCHEMA_MIGRATION_PREFIX = "20260201000000"
BASE_SCHEMA_MIGRATION_NAME = "skene_growth_schema"
PROCESSOR_MIGRATION_PREFIX = "20260202000000"
PROCESSOR_MIGRATION_NAME = "skene_growth_processor"


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


def ensure_base_schema_migration(output_dir: Path) -> Path | None:
    """Write base schema migration if it does not exist. Idempotent."""
    migrations_dir = output_dir / "supabase" / "migrations"
    migrations_dir.mkdir(parents=True, exist_ok=True)
    if list(migrations_dir.glob(f"*{BASE_SCHEMA_MIGRATION_NAME}*.sql")):
        return None
    path = migrations_dir / f"{BASE_SCHEMA_MIGRATION_PREFIX}_{BASE_SCHEMA_MIGRATION_NAME}.sql"
    path.write_text(BASE_SCHEMA_SQL, encoding="utf-8")
    return path


def ensure_processor_migration(output_dir: Path) -> Path | None:
    """Write processor migration if it does not exist. Idempotent."""
    migrations_dir = output_dir / "supabase" / "migrations"
    migrations_dir.mkdir(parents=True, exist_ok=True)
    if list(migrations_dir.glob(f"*{PROCESSOR_MIGRATION_NAME}*.sql")):
        return None
    path = migrations_dir / f"{PROCESSOR_MIGRATION_PREFIX}_{PROCESSOR_MIGRATION_NAME}.sql"
    path.write_text(PROCESSOR_SQL, encoding="utf-8")
    return path


def extract_supabase_telemetry(loop_def: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract telemetry items with type 'supabase' from a loop definition.
    """
    telemetry = loop_def.get("requirements", {}).get("telemetry", [])
    return [
        t
        for t in telemetry
        if isinstance(t, dict) and t.get("type") == "supabase"
    ]


def build_migration_sql(
    loops: list[dict[str, Any]],
    *,
    supabase_url_placeholder: str = "https://YOUR_PROJECT.supabase.co",
) -> str:
    """
    Build a complete Supabase migration SQL from growth loop definitions.

    Creates:
    - skene_growth schema and event_seq sequence
    - skene_growth.actions table for storing created actions
    - pg_net extension (if available)
    - One trigger function + trigger per telemetry item (table, operation)
    - Idempotent: DROP TRIGGER IF EXISTS before CREATE
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

    # Seed growth_loops from loop definitions (processor reads this)
    migration += "\n\n-- Seed growth_loops (upsert from loop definitions)\n"
    seen_loops: set[tuple[str, str]] = set()
    for loop_def in loops:
        loop_id = loop_def.get("loop_id", "growth_loop")
        for t in extract_supabase_telemetry(loop_def):
            table = t.get("table")
            op = (t.get("operation") or "INSERT").lower()
            if not table:
                continue
            trigger_event = f"{table.lower()}.{op}"
            loop_key = f"{loop_id}_{table.lower()}_{op}"
            key = (loop_key, trigger_event)
            if key in seen_loops:
                continue
            seen_loops.add(key)
            safe_key = loop_key.replace("'", "''")
            safe_event = trigger_event.replace("'", "''")
            migration += f"""
INSERT INTO skene_growth.growth_loops (loop_key, trigger_event, condition_config, action_type, action_config, recipient_path, enabled)
VALUES ('{safe_key}', '{safe_event}', '{{}}', 'email', '{{}}', 'email', true)
ON CONFLICT (loop_key) DO UPDATE SET trigger_event = EXCLUDED.trigger_event, enabled = EXCLUDED.enabled;
"""

    migration += "\n"

    return migration.strip()


def build_edge_function_index_ts(loops: list[dict[str, Any]]) -> str:
    """
    Build the skene-growth-process edge function.

    Acts as a secure proxy that forwards processor payloads to the centralized
    Skene Growth cloud API. Signs requests with HMAC for verification.
    Keeps logic centralized for instant updates without redeploying edge functions.
    """
    return '''// Skene Growth: Secure proxy to centralized cloud API (called by processor via pg_net)

import { HmacSha256 } from "https://deno.land/std@0.224.0/crypto/crypto.ts";
import { encodeHex } from "https://deno.land/std@0.224.0/encoding/hex.ts";

interface ProcessorPayload {
  source: string;
  event_log_id: number;
  loop_key: string;
  idempotency_key: string;
  recipient: string;
  enriched_payload: Record<string, unknown>;
  action_type: string;
  action_config: Record<string, unknown>;
}

async function signPayload(payload: string, secret: string): Promise<string> {
  const encoder = new TextEncoder();
  const keyData = encoder.encode(secret);
  const key = await crypto.subtle.importKey(
    "raw",
    keyData,
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(payload));
  return encodeHex(new Uint8Array(signature));
}

Deno.serve(async (req) => {
  try {
    const body: ProcessorPayload = await req.json();
    
    if (body.source !== "processor") {
      return new Response(JSON.stringify({ error: "Expected source=processor" }), {
        headers: { "Content-Type": "application/json" },
        status: 400,
      });
    }

    if (!body.recipient) {
      return new Response(JSON.stringify({ error: "Missing recipient" }), {
        headers: { "Content-Type": "application/json" },
        status: 400,
      });
    }

    // Get configuration from environment
    const SKENE_PROXY_SECRET = Deno.env.get("SKENE_PROXY_SECRET");
    const SKENE_CLOUD_ENDPOINT = Deno.env.get("SKENE_CLOUD_ENDPOINT") || "https://skene.ai/api/v1/cloud";
    const SUPABASE_PROJECT_REF = Deno.env.get("SUPABASE_PROJECT_REF") || "unknown";

    if (!SKENE_PROXY_SECRET) {
      console.error("[skene] SKENE_PROXY_SECRET not set. Deployment service must configure this secret.");
      return new Response(JSON.stringify({ error: "Configuration error" }), {
        headers: { "Content-Type": "application/json" },
        status: 500,
      });
    }

    // Sign the payload for verification by cloud API
    const timestamp = Date.now().toString();
    const payloadString = JSON.stringify(body);
    const signaturePayload = `${timestamp}.${payloadString}`;
    const signature = await signPayload(signaturePayload, SKENE_PROXY_SECRET);

    // Forward to centralized cloud API
    const cloudResponse = await fetch(SKENE_CLOUD_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Skene-Signature": signature,
        "X-Skene-Timestamp": timestamp,
        "X-Skene-Project-Ref": SUPABASE_PROJECT_REF,
      },
      body: payloadString,
    });

    if (!cloudResponse.ok) {
      const errorText = await cloudResponse.text();
      console.error("[skene] Cloud API error:", cloudResponse.status, errorText);
      return new Response(
        JSON.stringify({ 
          error: "Cloud execution failed", 
          status: cloudResponse.status 
        }),
        {
          headers: { "Content-Type": "application/json" },
          status: cloudResponse.status,
        }
      );
    }

    const result = await cloudResponse.json();
    return new Response(JSON.stringify(result), {
      headers: { "Content-Type": "application/json" },
      status: 200,
    });

  } catch (err) {
    console.error("[skene] Proxy error:", err);
    return new Response(JSON.stringify({ error: String(err) }), {
      headers: { "Content-Type": "application/json" },
      status: 500,
    });
  }
});
'''


def write_migration(
    migration_sql: str,
    output_dir: Path,
    *,
    migration_name: str = "skene_growth_telemetry",
) -> Path:
    """Write migration SQL to supabase/migrations/ with timestamp filename."""
    migrations_dir = output_dir / "supabase" / "migrations"
    migrations_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{timestamp}_{migration_name}.sql"
    path = migrations_dir / filename
    path.write_text(migration_sql, encoding="utf-8")
    return path


def write_edge_function(index_ts: str, output_dir: Path) -> Path:
    """Write edge function to supabase/functions/skene-growth-process/."""
    fn_dir = output_dir / "supabase" / "functions" / "skene-growth-process"
    fn_dir.mkdir(parents=True, exist_ok=True)
    path = fn_dir / "index.ts"
    path.write_text(index_ts, encoding="utf-8")
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


def push_deploy_to_upstream(
    project_root: Path,
    upstream_url: str,
    token: str,
    loops: list[dict[str, Any]],
    context: Path | None = None,
) -> dict[str, Any] | None:
    """
    Push deploy artifacts to upstream (migrations, edge function, growth-loops folder).
    Returns response dict on success, None on failure.
    """
    from skene_growth.growth_loops.upstream import push_to_upstream

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


def deploy_loops_to_supabase(
    loops: list[dict[str, Any]],
    output_dir: Path,
    *,
    supabase_url_placeholder: str = "https://YOUR_PROJECT.supabase.co",
) -> tuple[Path, Path]:
    """
    Build migration and edge function for the given growth loops.

    Ensures base schema migration exists (event_log, growth_loops, etc.) before
    writing trigger migration. Returns tuple of (migration_path, edge_function_path).
    """
    ensure_base_schema_migration(output_dir)
    ensure_processor_migration(output_dir)
    migration_sql = build_migration_sql(
        loops,
        supabase_url_placeholder=supabase_url_placeholder,
    )
    edge_ts = build_edge_function_index_ts(loops)

    migration_path = write_migration(migration_sql, output_dir)
    edge_path = write_edge_function(edge_ts, output_dir)

    return migration_path, edge_path
