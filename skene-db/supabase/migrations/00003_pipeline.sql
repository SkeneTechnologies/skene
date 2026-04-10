-- =============================================================================
-- Migration: 00003_pipeline
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
COMMENT ON COLUMN public.pipeline_stages.is_terminal IS 'Whether this stage represents a final state (won, lost, hired, rejected).';
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
