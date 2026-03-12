"""Shadow Mirror base schema for skene. All DDL is idempotent."""

BASE_SCHEMA_SQL = """
-- Skene Growth: Shadow Mirror base schema (event_log, failed_events, enrichment_map)
-- 1. Schema tables (run first, idempotent)
-- 2. Webhook (run after tables, idempotent): pg_net + notify_event_log

CREATE SCHEMA IF NOT EXISTS skene;

-- Universal sink for allowlisted triggers. Events land here before processing.
CREATE TABLE IF NOT EXISTS skene.event_log (
  id bigserial PRIMARY KEY,
  org_id uuid,
  entity_id uuid,
  event_type text NOT NULL,
  metadata jsonb DEFAULT '{}',
  occurred_at timestamptz DEFAULT now() NOT NULL,
  processed_at timestamptz,
  attempts int DEFAULT 0 NOT NULL,
  last_error text
);

-- Dead-letter table for events that exceed retry limit.
CREATE TABLE IF NOT EXISTS skene.failed_events (
  id bigserial PRIMARY KEY,
  event_log_id bigint NOT NULL,
  event_type text NOT NULL,
  payload jsonb DEFAULT '{}',
  failure_reason text,
  moved_at timestamptz DEFAULT now() NOT NULL
);

-- Enrichment rules: metadata_key -> enrich_sql (SQL returning jsonb to merge into metadata).
-- metadata_key matches event_type or '*' for all. enrich_sql uses $1=entity_id, $2=metadata.
CREATE TABLE IF NOT EXISTS skene.enrichment_map (
  metadata_key text PRIMARY KEY,
  enrich_sql text NOT NULL
);

-- BEFORE INSERT trigger on event_log: apply enrichment rules from enrichment_map.
CREATE OR REPLACE FUNCTION skene.enrich_event()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, skene
AS $$
DECLARE
  r RECORD;
  enriched jsonb;
BEGIN
  FOR r IN
    SELECT metadata_key, enrich_sql FROM skene.enrichment_map
    WHERE metadata_key = NEW.event_type OR metadata_key = '*'
  LOOP
    BEGIN
      EXECUTE r.enrich_sql INTO enriched USING NEW.entity_id, NEW.metadata;
      IF enriched IS NOT NULL THEN
        NEW.metadata := COALESCE(NEW.metadata, '{}'::jsonb) || enriched;
      END IF;
    EXCEPTION WHEN OTHERS THEN
      NULL;
    END;
  END LOOP;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS skene_trg_enrich_event ON skene.event_log;
CREATE TRIGGER skene_trg_enrich_event
  BEFORE INSERT ON skene.event_log
  FOR EACH ROW
  EXECUTE FUNCTION skene.enrich_event();

-- 2. Webhook: pg_net + notify_event_log
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_extension e
                JOIN pg_namespace n ON e.extnamespace = n.oid
                WHERE e.extname = 'pg_net' AND n.nspname = 'extensions') THEN
    CREATE EXTENSION IF NOT EXISTS pg_net WITH SCHEMA extensions;
  END IF;
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'pg_net not available: %. Enable it in Supabase dashboard.', SQLERRM;
END $$;

-- AFTER INSERT trigger on event_log: POST to ingest_url via pg_net.
-- Set app.settings.ingest_url for the webhook endpoint.
CREATE OR REPLACE FUNCTION skene.notify_event_log()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, skene
AS $$
DECLARE
  ingest_url text;
BEGIN
  ingest_url := nullif(trim(current_setting('app.settings.ingest_url', true)), '');
  IF ingest_url IS NOT NULL THEN
    PERFORM net.http_post(
      url := ingest_url,
      headers := '{"Content-Type": "application/json"}'::jsonb,
      body := jsonb_build_object(
        'id', NEW.id,
        'org_id', NEW.org_id,
        'entity_id', NEW.entity_id,
        'event_type', NEW.event_type,
        'metadata', NEW.metadata,
        'occurred_at', NEW.occurred_at
      )
    );
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS skene_trg_notify_event_log ON skene.event_log;
CREATE TRIGGER skene_trg_notify_event_log
  AFTER INSERT ON skene.event_log
  FOR EACH ROW
  EXECUTE FUNCTION skene.notify_event_log();
""".strip()
