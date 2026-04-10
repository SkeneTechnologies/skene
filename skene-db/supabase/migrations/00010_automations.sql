-- =============================================================================
-- Migration: 00010_automations
-- Description: Automation definitions, actions, and run logs.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Enums
-- -----------------------------------------------------------------------------
CREATE TYPE public.automation_trigger_type AS ENUM ('event', 'schedule', 'webhook', 'manual');
CREATE TYPE public.automation_status AS ENUM ('active', 'paused', 'draft', 'archived');
CREATE TYPE public.run_status AS ENUM ('pending', 'running', 'completed', 'failed');

-- -----------------------------------------------------------------------------
-- Table: automations
-- Automation definitions with trigger conditions.
-- -----------------------------------------------------------------------------
CREATE TABLE public.automations (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  creator_id      uuid REFERENCES public.users(id) ON DELETE SET NULL,
  name            text NOT NULL,
  description     text,
  trigger_type    public.automation_trigger_type NOT NULL,
  trigger_config  jsonb NOT NULL DEFAULT '{}'::jsonb,
  status          public.automation_status NOT NULL DEFAULT 'draft',
  last_run_at     timestamptz,
  run_count       integer NOT NULL DEFAULT 0,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.automations IS 'Automation definitions. Trigger type + config determines when it runs.';
COMMENT ON COLUMN public.automations.trigger_config IS 'JSON config for the trigger (e.g. cron expression, event filter, webhook URL).';

CREATE INDEX idx_automations_org_id ON public.automations(org_id);
CREATE INDEX idx_automations_status ON public.automations(status);
CREATE INDEX idx_automations_trigger_type ON public.automations(trigger_type);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.automations
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: automation_actions
-- Ordered actions within an automation.
-- -----------------------------------------------------------------------------
CREATE TABLE public.automation_actions (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  automation_id   uuid NOT NULL REFERENCES public.automations(id) ON DELETE CASCADE,
  action_type     text NOT NULL,
  action_config   jsonb NOT NULL DEFAULT '{}'::jsonb,
  position        integer NOT NULL DEFAULT 0,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.automation_actions IS 'Ordered steps within an automation. position determines execution order.';
COMMENT ON COLUMN public.automation_actions.action_type IS 'What this step does (e.g. send_email, update_field, create_task, webhook).';
COMMENT ON COLUMN public.automation_actions.action_config IS 'JSON config for the action (template, field mappings, URL, etc).';

CREATE INDEX idx_automation_actions_org_id ON public.automation_actions(org_id);
CREATE INDEX idx_automation_actions_automation_id ON public.automation_actions(automation_id);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.automation_actions
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: automation_runs
-- Execution log for automations.
-- -----------------------------------------------------------------------------
CREATE TABLE public.automation_runs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  automation_id   uuid NOT NULL REFERENCES public.automations(id) ON DELETE CASCADE,
  status          public.run_status NOT NULL DEFAULT 'pending',
  started_at      timestamptz,
  completed_at    timestamptz,
  error_message   text,
  result          jsonb DEFAULT '{}'::jsonb,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.automation_runs IS 'Execution log. One row per automation run with status and result.';

CREATE INDEX idx_automation_runs_org_id ON public.automation_runs(org_id);
CREATE INDEX idx_automation_runs_automation_id ON public.automation_runs(automation_id);
CREATE INDEX idx_automation_runs_status ON public.automation_runs(status);
CREATE INDEX idx_automation_runs_started_at ON public.automation_runs(started_at);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.automation_runs
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
