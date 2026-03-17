"""Skene Growth event_log schema and webhook. All DDL is idempotent."""

DB_TRIGGER_PATH = "/api/v1/cloud/ingest/db-trigger"

# Placeholders for notify_event_log when not overridden by --local
DEFAULT_UPSTREAM_INGEST_URL = "https://YOUR_UPSTREAM_INGEST_URL"
DEFAULT_PROXY_SECRET = "YOUR_PROXY_SECRET"

_TABLES_SQL = """\
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

DROP TABLE IF EXISTS skene_growth.enrichment_map;
CREATE TABLE skene_growth.enrichment_map (
  trigger_event text NOT NULL,
  metadata_key  text NOT NULL,
  enrich_sql    text,
  strip_after   boolean DEFAULT false,
  PRIMARY KEY (trigger_event, metadata_key)
);"""

_ENRICH_EVENT_SQL = """\
CREATE OR REPLACE FUNCTION skene_growth.enrich_event()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, skene_growth
AS $$
DECLARE
  rule        RECORD;
  _result     jsonb;
  _strip_keys text[] := ARRAY[]::text[];
BEGIN
  FOR rule IN
    SELECT metadata_key, enrich_sql, strip_after
    FROM skene_growth.enrichment_map
    WHERE trigger_event = NEW.event_type
      AND NEW.metadata ? metadata_key
  LOOP
    BEGIN
      IF rule.enrich_sql IS NOT NULL THEN
        EXECUTE rule.enrich_sql INTO _result USING (NEW.metadata->>rule.metadata_key);
        IF _result IS NOT NULL THEN
          NEW.metadata = NEW.metadata || _result;
        END IF;
      END IF;
      IF rule.strip_after THEN
        _strip_keys := _strip_keys || rule.metadata_key;
      END IF;
    EXCEPTION WHEN OTHERS THEN
      NULL;
    END;
  END LOOP;
  IF array_length(_strip_keys, 1) > 0 THEN
    NEW.metadata = NEW.metadata - _strip_keys;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS skene_growth_enrich_event ON skene_growth.event_log;
CREATE TRIGGER skene_growth_enrich_event
  BEFORE INSERT ON skene_growth.event_log
  FOR EACH ROW
  EXECUTE FUNCTION skene_growth.enrich_event();"""

_WEBHOOK_TRIGGER_SQL = """\
DROP TRIGGER IF EXISTS skene_growth_webhook_event_log ON skene_growth.event_log;
CREATE TRIGGER skene_growth_webhook_event_log
  AFTER INSERT ON skene_growth.event_log
  FOR EACH ROW
  EXECUTE FUNCTION skene_growth.notify_event_log();"""


def _notify_event_log_function_sql(ingest_url: str, proxy_secret: str) -> str:
    """Return CREATE OR REPLACE for notify_event_log with the given URL and secret baked in."""
    return f"""\
CREATE OR REPLACE FUNCTION skene_growth.notify_event_log()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, skene_growth, net
AS $$
DECLARE
  payload jsonb;
  ingest_url text := '{ingest_url}';
  proxy_secret text := '{proxy_secret}';
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
$$;"""


BASE_SCHEMA_SQL = "\n\n".join(
    [
        _TABLES_SQL,
        _ENRICH_EVENT_SQL,
        "CREATE EXTENSION IF NOT EXISTS pg_net;",
        _notify_event_log_function_sql(
            DEFAULT_UPSTREAM_INGEST_URL + DB_TRIGGER_PATH,
            DEFAULT_PROXY_SECRET,
        ),
        _WEBHOOK_TRIGGER_SQL,
    ]
)


def _normalize_ingest_url(url: str) -> str:
    """Return full webhook URL, appending db-trigger path only if not already present."""
    base = url.rstrip("/")
    if base.endswith(DB_TRIGGER_PATH):
        return base
    return f"{base}{DB_TRIGGER_PATH}"


def notify_event_log_sql(upstream_ingest_url: str, proxy_secret: str) -> str:
    """
    Generate CREATE OR REPLACE for notify_event_log with given upstream ingest URL and proxy secret.
    Use when --local URL is provided to override the default placeholders.
    """
    full_url = _normalize_ingest_url(upstream_ingest_url)
    sql = _notify_event_log_function_sql(
        full_url.replace("'", "''"),
        proxy_secret.replace("'", "''"),
    )
    return "-- Webhook override: upstream ingest URL and proxy secret from --local\n" + sql
