"""Skene Growth event_log schema and webhook. All DDL is idempotent."""

# Placeholders for notify_event_log when not overridden by --local
DEFAULT_INGEST_URL = "https://YOUR_INGEST_URL"
DEFAULT_PROXY_SECRET = "YOUR_PROXY_SECRET"

# Base schema: tables + enrich_event + notify_event_log (with placeholders)
BASE_SCHEMA_SQL = (
    """
-- Skene Growth: event_log, failed_events, enrichment_map
-- 1. Schema tables
-- 2. enrich_event (BEFORE INSERT)
-- 3. pg_net + notify_event_log (AFTER INSERT)

CREATE SCHEMA IF NOT EXISTS skene_growth;

CREATE TABLE IF NOT EXISTS skene_growth.event_log (
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

CREATE TABLE IF NOT EXISTS skene_growth.failed_events (
  id bigserial PRIMARY KEY,
  event_log_id bigint NOT NULL,
  event_type text NOT NULL,
  payload jsonb DEFAULT '{}',
  failure_reason text,
  moved_at timestamptz DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS skene_growth.enrichment_map (
  metadata_key text PRIMARY KEY,
  enrich_sql text NOT NULL
);

CREATE OR REPLACE FUNCTION skene_growth.enrich_event()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, skene_growth
AS $$
DECLARE
  rule RECORD;
  _result jsonb;
  _lookup_value text;
  _map_exists boolean;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'skene_growth' AND table_name = 'enrichment_map'
  ) INTO _map_exists;
  IF NOT _map_exists THEN
    RETURN NEW;
  END IF;
  FOR rule IN
    SELECT metadata_key, enrich_sql FROM skene_growth.enrichment_map
    WHERE NEW.metadata ? metadata_key
  LOOP
    BEGIN
      _lookup_value := NEW.metadata->>rule.metadata_key;
      IF _lookup_value IS NULL OR _lookup_value = '' THEN
        CONTINUE;
      END IF;
      EXECUTE rule.enrich_sql INTO _result USING _lookup_value;
      IF _result IS NOT NULL THEN
        NEW.metadata = NEW.metadata || _result;
      END IF;
    EXCEPTION WHEN OTHERS THEN
      NULL;
    END;
  END LOOP;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS skene_growth_enrich_event ON skene_growth.event_log;
CREATE TRIGGER skene_growth_enrich_event
  BEFORE INSERT ON skene_growth.event_log
  FOR EACH ROW
  EXECUTE FUNCTION skene_growth.enrich_event();

CREATE EXTENSION IF NOT EXISTS pg_net;

CREATE OR REPLACE FUNCTION skene_growth.notify_event_log()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, skene_growth, net
AS $$
DECLARE
  payload jsonb;
  ingest_url text := '"""
    + DEFAULT_INGEST_URL
    + """/api/v1/cloud/ingest/db-trigger';
  proxy_secret text := '"""
    + DEFAULT_PROXY_SECRET
    + """';
BEGIN
  payload := jsonb_build_object(
    'type', 'INSERT',
    'table', 'event_log',
    'schema', 'skene_growth',
    'record', to_jsonb(NEW),
    'old_record', null
  );
  PERFORM net.http_post(
    url := ingest_url,
    body := payload,
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'x-skene-secret', proxy_secret
    ),
    timeout_milliseconds := 5000
  );
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS skene_growth_webhook_event_log ON skene_growth.event_log;
CREATE TRIGGER skene_growth_webhook_event_log
  AFTER INSERT ON skene_growth.event_log
  FOR EACH ROW
  EXECUTE FUNCTION skene_growth.notify_event_log();
""".strip()
)


def notify_event_log_sql(ingest_url: str, proxy_secret: str) -> str:
    """
    Generate CREATE OR REPLACE for notify_event_log with given ingest URL and proxy secret.
    Use when --local URL is provided to override the default placeholders.
    """
    # Escape single quotes for SQL string literals
    url_escaped = ingest_url.rstrip("/").replace("'", "''")
    secret_escaped = proxy_secret.replace("'", "''")
    return f"""
-- Webhook override: ingest URL and proxy secret from --local
CREATE OR REPLACE FUNCTION skene_growth.notify_event_log()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, skene_growth, net
AS $$
DECLARE
  payload jsonb;
  ingest_url text := '{url_escaped}/api/v1/cloud/ingest/db-trigger';
  proxy_secret text := '{secret_escaped}';
BEGIN
  payload := jsonb_build_object(
    'type', 'INSERT',
    'table', 'event_log',
    'schema', 'skene_growth',
    'record', to_jsonb(NEW),
    'old_record', null
  );
  PERFORM net.http_post(
    url := ingest_url,
    body := payload,
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'x-skene-secret', proxy_secret
    ),
    timeout_milliseconds := 5000
  );
  RETURN NEW;
END;
$$;
""".strip()
