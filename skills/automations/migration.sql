-- =============================================================================
-- Skill: automations
-- Depends on: identity
-- Description: Trigger-based automations with action sequences and run history.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Enums
-- -----------------------------------------------------------------------------
CREATE TYPE public.automation_trigger_type AS ENUM ('event', 'schedule', 'webhook', 'manual');
CREATE TYPE public.automation_status AS ENUM ('active', 'paused', 'draft', 'archived');
CREATE TYPE public.run_status AS ENUM ('pending', 'running', 'completed', 'failed');

-- -----------------------------------------------------------------------------
-- Table: automations
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

COMMENT ON COLUMN public.automations.trigger_config IS 'JSON: cron expression, event filter, webhook URL, etc.';

CREATE INDEX idx_automations_org_id ON public.automations(org_id);
CREATE INDEX idx_automations_status ON public.automations(status);
CREATE INDEX idx_automations_trigger_type ON public.automations(trigger_type);

CREATE TRIGGER trg_automations_updated_at BEFORE UPDATE ON public.automations
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: automation_actions
-- Ordered steps within an automation.
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

COMMENT ON COLUMN public.automation_actions.action_type IS 'send_email, update_field, create_task, webhook, etc.';
COMMENT ON COLUMN public.automation_actions.action_config IS 'JSON config for the action.';
COMMENT ON COLUMN public.automation_actions.position IS 'Execution order within the automation.';

CREATE INDEX idx_automation_actions_org_id ON public.automation_actions(org_id);
CREATE INDEX idx_automation_actions_automation_id ON public.automation_actions(automation_id);

CREATE TRIGGER trg_automation_actions_updated_at BEFORE UPDATE ON public.automation_actions
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: automation_runs
-- One row per execution of an automation.
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

COMMENT ON TABLE public.automation_runs IS 'One row per execution of an automation.';

CREATE INDEX idx_automation_runs_org_id ON public.automation_runs(org_id);
CREATE INDEX idx_automation_runs_automation_id ON public.automation_runs(automation_id);
CREATE INDEX idx_automation_runs_status ON public.automation_runs(status);
CREATE INDEX idx_automation_runs_started_at ON public.automation_runs(started_at);

CREATE TRIGGER trg_automation_runs_updated_at BEFORE UPDATE ON public.automation_runs
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- RLS
-- -----------------------------------------------------------------------------

-- automations
ALTER TABLE public.automations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "automations_select" ON public.automations
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "automations_insert" ON public.automations
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "automations_update" ON public.automations
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "automations_delete" ON public.automations
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- automation_actions
ALTER TABLE public.automation_actions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "automation_actions_select" ON public.automation_actions
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "automation_actions_insert" ON public.automation_actions
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "automation_actions_update" ON public.automation_actions
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "automation_actions_delete" ON public.automation_actions
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- automation_runs
ALTER TABLE public.automation_runs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "automation_runs_select" ON public.automation_runs
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "automation_runs_insert" ON public.automation_runs
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "automation_runs_update" ON public.automation_runs
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "automation_runs_delete" ON public.automation_runs
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());
