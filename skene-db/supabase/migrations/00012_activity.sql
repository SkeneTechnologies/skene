-- =============================================================================
-- Migration: 00012_activity
-- Description: Polymorphic activity log. Audit trail for every entity.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Enums
-- -----------------------------------------------------------------------------
CREATE TYPE public.activity_action AS ENUM (
  'created', 'updated', 'deleted', 'status_changed',
  'assigned', 'commented', 'viewed', 'email_sent',
  'email_received', 'note_added', 'call_logged',
  'stage_changed', 'deal_won', 'deal_lost',
  'task_completed', 'payment_received'
);

-- -----------------------------------------------------------------------------
-- Table: activities
-- Append-only audit log. Records every significant action on any entity.
-- -----------------------------------------------------------------------------
CREATE TABLE public.activities (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  actor_id        uuid REFERENCES public.users(id) ON DELETE SET NULL,
  entity_type     text NOT NULL,
  entity_id       uuid NOT NULL,
  action          public.activity_action NOT NULL,
  description     text,
  changes         jsonb,
  occurred_at     timestamptz NOT NULL DEFAULT now(),
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb,
  CHECK (entity_type IN ('contact', 'company', 'deal', 'task', 'ticket', 'document', 'project', 'subscription', 'invoice', 'event'))
);

COMMENT ON TABLE public.activities IS 'Append-only audit log. Every significant action on any entity gets a row here.';
COMMENT ON COLUMN public.activities.actor_id IS 'The user who performed the action. NULL for system-generated activities.';
COMMENT ON COLUMN public.activities.changes IS 'JSON diff of what changed (e.g. {"status": {"from": "open", "to": "closed"}}).';
COMMENT ON COLUMN public.activities.occurred_at IS 'When the action actually happened. May differ from created_at for imported data.';

CREATE INDEX idx_activities_org_id ON public.activities(org_id);
CREATE INDEX idx_activities_entity ON public.activities(entity_type, entity_id);
CREATE INDEX idx_activities_actor_id ON public.activities(actor_id);
CREATE INDEX idx_activities_action ON public.activities(action);
CREATE INDEX idx_activities_occurred_at ON public.activities(occurred_at);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.activities
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
