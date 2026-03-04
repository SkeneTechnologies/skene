"""Shadow Mirror base schema for skene_growth. All DDL is idempotent."""

BASE_SCHEMA_SQL = """
-- Skene Growth: Shadow Mirror base schema (event_log, growth_loops, loop_executions, attribution, failed_events)
-- Idempotent: safe to run on init or every deploy

CREATE SCHEMA IF NOT EXISTS skene_growth;

-- Universal sink for allowlisted triggers. Events land here before processing.
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

-- Loop registry: config-driven (trigger_event, condition_config, action_type, recipient_path).
CREATE TABLE IF NOT EXISTS skene_growth.growth_loops (
  loop_key text PRIMARY KEY,
  trigger_event text NOT NULL,
  condition_config jsonb DEFAULT '{}',
  action_type text NOT NULL,
  action_config jsonb DEFAULT '{}',
  recipient_path text,
  enabled boolean DEFAULT true NOT NULL
);

-- Idempotency and execution tracking. Processor creates rows here before calling Cloud.
CREATE TABLE IF NOT EXISTS skene_growth.loop_executions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_log_id bigint NOT NULL REFERENCES skene_growth.event_log(id),
  idempotency_key text UNIQUE NOT NULL,
  status text NOT NULL CHECK (status IN ('pending', 'sent', 'failed')),
  tokens_used int DEFAULT 0,
  error_message text,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL
);

-- Attribution for billing.
CREATE TABLE IF NOT EXISTS skene_growth.attribution (
  loop_execution_id uuid PRIMARY KEY REFERENCES skene_growth.loop_executions(id),
  conversion_event text NOT NULL,
  conversion_value_usd decimal(12, 2)
);

-- Dead-letter table for events that exceed retry limit.
CREATE TABLE IF NOT EXISTS skene_growth.failed_events (
  id bigserial PRIMARY KEY,
  event_log_id bigint NOT NULL,
  event_type text NOT NULL,
  payload jsonb DEFAULT '{}',
  failure_reason text,
  moved_at timestamptz DEFAULT now() NOT NULL
);

-- Patch: Constraint updates (drop-then-add pattern for schema evolution)
-- Ensures constraint matches latest definition on every deploy.
ALTER TABLE skene_growth.loop_executions
DROP CONSTRAINT IF EXISTS loop_executions_status_check;

ALTER TABLE skene_growth.loop_executions
ADD CONSTRAINT loop_executions_status_check
CHECK (status IN ('pending', 'sent', 'failed', 'retrying', 'archived'));

-- Patch: Future column additions use the DO block pattern, e.g.:
-- DO $$
-- BEGIN
--   IF NOT EXISTS (SELECT 1 FROM information_schema.columns
--                  WHERE table_schema='skene_growth' AND table_name='event_log' AND column_name='version') THEN
--     ALTER TABLE skene_growth.event_log ADD COLUMN version text DEFAULT '1.0';
--   END IF;
-- END $$;
""".strip()
