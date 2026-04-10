-- =============================================================================
-- Skill: pipeline
-- Depends on: crm (contacts, companies)
-- Description: Sales/recruiting pipelines, stages, deals, and stage history.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Enums
-- -----------------------------------------------------------------------------
CREATE TYPE public.deal_status AS ENUM ('open', 'won', 'lost', 'stale');

-- -----------------------------------------------------------------------------
-- Table: pipelines
-- A pipeline is a workflow with ordered stages (e.g. Sales, Recruiting).
-- -----------------------------------------------------------------------------
CREATE TABLE public.pipelines (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  name            text NOT NULL,
  description     text,
  is_default      boolean NOT NULL DEFAULT false,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.pipelines IS 'Named workflows with ordered stages. E.g. Sales pipeline, Recruiting pipeline.';

CREATE INDEX idx_pipelines_org_id ON public.pipelines(org_id);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.pipelines
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: pipeline_stages
-- Ordered stages within a pipeline.
-- -----------------------------------------------------------------------------
CREATE TABLE public.pipeline_stages (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  pipeline_id     uuid NOT NULL REFERENCES public.pipelines(id) ON DELETE CASCADE,
  name            text NOT NULL,
  position        integer NOT NULL DEFAULT 0,
  color           text,
  is_terminal     boolean NOT NULL DEFAULT false,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb,
  UNIQUE(pipeline_id, position)
);

COMMENT ON TABLE public.pipeline_stages IS 'Ordered stages within a pipeline. position determines display order.';
COMMENT ON COLUMN public.pipeline_stages.position IS 'Display order within the pipeline.';
COMMENT ON COLUMN public.pipeline_stages.is_terminal IS 'Whether this stage represents a final state (e.g. Closed Won, Rejected).';
COMMENT ON COLUMN public.pipeline_stages.color IS 'Hex color for UI rendering.';

CREATE INDEX idx_pipeline_stages_org_id ON public.pipeline_stages(org_id);
CREATE INDEX idx_pipeline_stages_pipeline_id ON public.pipeline_stages(pipeline_id);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.pipeline_stages
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: deals
-- An opportunity moving through a pipeline.
-- -----------------------------------------------------------------------------
CREATE TABLE public.deals (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  pipeline_id     uuid NOT NULL REFERENCES public.pipelines(id) ON DELETE CASCADE,
  stage_id        uuid REFERENCES public.pipeline_stages(id) ON DELETE SET NULL,
  owner_id        uuid REFERENCES public.users(id) ON DELETE SET NULL,
  contact_id      uuid REFERENCES public.contacts(id) ON DELETE SET NULL,
  company_id      uuid REFERENCES public.companies(id) ON DELETE SET NULL,
  title           text NOT NULL,
  value           numeric DEFAULT 0,
  currency        text DEFAULT 'USD',
  status          public.deal_status NOT NULL DEFAULT 'open',
  expected_close_date date,
  closed_at       timestamptz,
  lost_reason     text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.deals IS 'An opportunity moving through a pipeline. Tracks value, status, and stage.';
COMMENT ON COLUMN public.deals.value IS 'Deal value in smallest currency unit (cents).';
COMMENT ON COLUMN public.deals.lost_reason IS 'Free-text explanation when status is lost.';

CREATE INDEX idx_deals_org_id ON public.deals(org_id);
CREATE INDEX idx_deals_pipeline_id ON public.deals(pipeline_id);
CREATE INDEX idx_deals_stage_id ON public.deals(stage_id);
CREATE INDEX idx_deals_owner_id ON public.deals(owner_id);
CREATE INDEX idx_deals_status ON public.deals(status);
CREATE INDEX idx_deals_contact_id ON public.deals(contact_id);
CREATE INDEX idx_deals_company_id ON public.deals(company_id);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.deals
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: deal_stage_history
-- Immutable log of every stage change for a deal.
-- -----------------------------------------------------------------------------
CREATE TABLE public.deal_stage_history (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  deal_id         uuid NOT NULL REFERENCES public.deals(id) ON DELETE CASCADE,
  from_stage_id   uuid REFERENCES public.pipeline_stages(id) ON DELETE SET NULL,
  to_stage_id     uuid REFERENCES public.pipeline_stages(id) ON DELETE SET NULL,
  changed_by      uuid REFERENCES public.users(id) ON DELETE SET NULL,
  changed_at      timestamptz NOT NULL DEFAULT now(),
  duration_seconds integer,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.deal_stage_history IS 'Append-only log of deal stage transitions. Used for pipeline analytics.';
COMMENT ON COLUMN public.deal_stage_history.duration_seconds IS 'Time spent in the previous stage.';

CREATE INDEX idx_deal_stage_history_org_id ON public.deal_stage_history(org_id);
CREATE INDEX idx_deal_stage_history_deal_id ON public.deal_stage_history(deal_id);
CREATE INDEX idx_deal_stage_history_changed_at ON public.deal_stage_history(changed_at);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.deal_stage_history
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- RLS
-- -----------------------------------------------------------------------------

-- pipelines
ALTER TABLE public.pipelines ENABLE ROW LEVEL SECURITY;

CREATE POLICY "pipelines_select" ON public.pipelines
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "pipelines_insert" ON public.pipelines
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "pipelines_update" ON public.pipelines
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "pipelines_delete" ON public.pipelines
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- pipeline_stages
ALTER TABLE public.pipeline_stages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "pipeline_stages_select" ON public.pipeline_stages
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "pipeline_stages_insert" ON public.pipeline_stages
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "pipeline_stages_update" ON public.pipeline_stages
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "pipeline_stages_delete" ON public.pipeline_stages
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- deals
ALTER TABLE public.deals ENABLE ROW LEVEL SECURITY;

CREATE POLICY "deals_select" ON public.deals
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "deals_insert" ON public.deals
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "deals_update" ON public.deals
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "deals_delete" ON public.deals
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- deal_stage_history
ALTER TABLE public.deal_stage_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY "deal_stage_history_select" ON public.deal_stage_history
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "deal_stage_history_insert" ON public.deal_stage_history
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "deal_stage_history_update" ON public.deal_stage_history
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "deal_stage_history_delete" ON public.deal_stage_history
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());
