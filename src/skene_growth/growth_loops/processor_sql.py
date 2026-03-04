"""Shadow Mirror processor: PL/pgSQL that reads event_log, enriches, evaluates, calls Cloud."""

PROCESSOR_SQL = """
-- Skene Growth: Processor (reads event_log -> enrich -> evaluate condition_config -> call edge function proxy)
-- Edge function forwards to centralized cloud API with HMAC signature for secure orchestration.
-- Run via pg_cron: SELECT cron.schedule('skene_process', '* * * * *', 'SELECT skene_growth.process_events()');

-- Ensure pg_net extension is available (safe for third-party deploy keys)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_extension e
                JOIN pg_namespace n ON e.extnamespace = n.oid
                WHERE e.extname = 'pg_net' AND n.nspname = 'extensions') THEN
    CREATE EXTENSION IF NOT EXISTS pg_net WITH SCHEMA extensions;
  END IF;
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'pg_net not available: %. Client may need to enable it in Supabase dashboard.', SQLERRM;
END $$;

CREATE OR REPLACE FUNCTION skene_growth.process_events()
RETURNS int
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, skene_growth
AS $$
DECLARE
  r RECORD;
  loop_rec RECORD;
  enriched jsonb;
  recipient text;
  idem_key text;
  exec_id uuid;
  max_attempts int := 3;
  processed_count int := 0;
  req_id bigint;
BEGIN
  FOR r IN
    SELECT id, event_type, metadata, entity_id
    FROM skene_growth.event_log
    WHERE processed_at IS NULL AND attempts < max_attempts
    ORDER BY id
    LIMIT 50
  LOOP
    BEGIN
      -- Enrich: metadata + resolve email from workspace_id or user_id (Supabase pattern)
      enriched := r.metadata;
      enriched := jsonb_set(
        COALESCE(enriched, '{}'::jsonb),
        '{db_id}',
        to_jsonb(COALESCE(r.entity_id::text, (r.metadata->>'id'), r.id::text))
      );

      IF r.metadata ? 'workspace_id' AND to_regclass('public.workspaces') IS NOT NULL THEN
        SELECT u.email INTO recipient
        FROM public.workspaces w
        LEFT JOIN auth.users u ON u.id = w.owner_id
        WHERE w.id = (r.metadata->>'workspace_id')::uuid
        LIMIT 1;
        IF recipient IS NOT NULL THEN
          enriched := jsonb_set(enriched, '{email}', to_jsonb(recipient));
          enriched := jsonb_set(enriched, '{user_id}', r.metadata->'workspace_id');
        END IF;
      END IF;

      IF recipient IS NULL AND r.metadata ? 'user_id' AND to_regclass('auth.users') IS NOT NULL THEN
        SELECT email INTO recipient FROM auth.users WHERE id = (r.metadata->>'user_id')::uuid LIMIT 1;
        IF recipient IS NOT NULL THEN
          enriched := jsonb_set(enriched, '{email}', to_jsonb(recipient));
        END IF;
      END IF;

      recipient := NULL;

      -- Match enabled loops for this event_type
      FOR loop_rec IN
        SELECT loop_key, action_type, action_config, recipient_path, condition_config
        FROM skene_growth.growth_loops
        WHERE trigger_event = r.event_type AND enabled = true
      LOOP
        -- Evaluate condition_config: empty or {} means pass
        IF loop_rec.condition_config IS NULL OR loop_rec.condition_config = '{}'::jsonb THEN
          NULL;  -- pass
        ELSE
          CONTINUE;  -- MVP: non-empty condition_config skips (full eval in future)
        END IF;

        -- Resolve recipient from recipient_path (dot path into enriched)
        IF loop_rec.recipient_path IS NOT NULL AND loop_rec.recipient_path != '' THEN
          recipient := enriched #>> string_to_array(loop_rec.recipient_path, '.');
        ELSE
          recipient := enriched->>'email';
        END IF;

        IF recipient IS NULL OR recipient = '' THEN
          CONTINUE;  -- No recipient, skip
        END IF;

        idem_key := r.id::text || '_' || loop_rec.loop_key;

        -- Create loop_executions (pending); skip if idempotency key exists
        INSERT INTO skene_growth.loop_executions (event_log_id, idempotency_key, status)
        VALUES (r.id, idem_key, 'pending')
        ON CONFLICT (idempotency_key) DO NOTHING;
        IF NOT FOUND THEN
          CONTINUE;
        END IF;
        SELECT id INTO exec_id FROM skene_growth.loop_executions WHERE idempotency_key = idem_key;

        -- Call edge function proxy via pg_net (forwards to cloud API). Uses supabase_service_role_key or supabase_anon_key.
        SELECT net.http_post(
          url := current_setting('app.settings.supabase_url', true) || '/functions/v1/skene-growth-process',
          headers := jsonb_build_object(
            'Content-Type', 'application/json',
            'Authorization', 'Bearer ' || COALESCE(
              nullif(current_setting('app.settings.supabase_service_role_key', true), ''),
              nullif(current_setting('app.settings.supabase_anon_key', true), '')
            )
          ),
          body := jsonb_build_object(
            'source', 'processor',
            'event_log_id', r.id,
            'loop_key', loop_rec.loop_key,
            'idempotency_key', idem_key,
            'recipient', recipient,
            'enriched_payload', enriched,
            'action_type', loop_rec.action_type,
            'action_config', COALESCE(loop_rec.action_config, '{}'::jsonb)
          )
        ) INTO req_id;

        -- Mark sent (async; real implementation would poll or use callback)
        UPDATE skene_growth.loop_executions SET status = 'sent', updated_at = now() WHERE id = exec_id;
      END LOOP;

      UPDATE skene_growth.event_log SET processed_at = now() WHERE id = r.id;
      processed_count := processed_count + 1;

    EXCEPTION WHEN OTHERS THEN
      UPDATE skene_growth.event_log
      SET attempts = attempts + 1, last_error = SQLERRM
      WHERE id = r.id;

      IF (SELECT attempts FROM skene_growth.event_log WHERE id = r.id) >= max_attempts THEN
        INSERT INTO skene_growth.failed_events (event_log_id, event_type, payload, failure_reason)
        VALUES (r.id, r.event_type, r.metadata, SQLERRM);
      END IF;
    END;
  END LOOP;

  RETURN processed_count;
END;
$$;

COMMENT ON FUNCTION skene_growth.process_events() IS 'Shadow Mirror processor: read event_log, enrich, evaluate growth_loops, call edge function proxy. Schedule via pg_cron.';

-- pg_cron: idempotent schedule (requires pg_cron enabled in Supabase dashboard)
DO $$
BEGIN
  IF to_regclass('cron.job') IS NOT NULL THEN
    PERFORM cron.unschedule('skene_process');
    PERFORM cron.schedule('skene_process', '* * * * *', 'SELECT skene_growth.process_events();');
  ELSE
    RAISE NOTICE 'pg_cron not available. Enable it in the Supabase dashboard to schedule process_events().';
  END IF;
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'pg_cron scheduling skipped: %', SQLERRM;
END $$;
""".strip()
