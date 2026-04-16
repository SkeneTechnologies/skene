-- approvals skill: chains, steps, requests, decisions, and delegations
-- Depends on identity.

-- =============================================================================
-- 1. Enums
-- =============================================================================

CREATE TYPE public.approval_status AS ENUM ('pending', 'approved', 'rejected', 'canceled');
CREATE TYPE public.approval_decision AS ENUM ('approved', 'rejected');

-- =============================================================================
-- 2. Tables
-- =============================================================================

CREATE TABLE public.approval_chains (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid        NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  name             text        NOT NULL,
  description      text,
  entity_type      text        NOT NULL,
  is_active        boolean     NOT NULL DEFAULT true,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  metadata         jsonb       DEFAULT '{}'::jsonb
);

CREATE TABLE public.approval_steps (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid        NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  chain_id         uuid        NOT NULL REFERENCES public.approval_chains (id) ON DELETE CASCADE,
  position         integer     NOT NULL,
  approver_id      uuid        REFERENCES public.users (id) ON DELETE SET NULL,
  approver_role    text,
  is_required      boolean     NOT NULL DEFAULT true,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  metadata         jsonb       DEFAULT '{}'::jsonb
);

CREATE TABLE public.approval_requests (
  id               uuid                  PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid                  NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  chain_id         uuid                  NOT NULL REFERENCES public.approval_chains (id) ON DELETE CASCADE,
  entity_type      text                  NOT NULL,
  entity_id        uuid                  NOT NULL,
  requester_id     uuid                  REFERENCES public.users (id) ON DELETE SET NULL,
  status           public.approval_status NOT NULL DEFAULT 'pending',
  submitted_at     timestamptz           NOT NULL DEFAULT now(),
  resolved_at      timestamptz,
  created_at       timestamptz           NOT NULL DEFAULT now(),
  updated_at       timestamptz           NOT NULL DEFAULT now(),
  metadata         jsonb                 DEFAULT '{}'::jsonb
);

CREATE TABLE public.approval_decisions (
  id               uuid                    PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid                    NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  request_id       uuid                    NOT NULL REFERENCES public.approval_requests (id) ON DELETE CASCADE,
  step_id          uuid                    REFERENCES public.approval_steps (id) ON DELETE SET NULL,
  decided_by       uuid                    REFERENCES public.users (id) ON DELETE SET NULL,
  decision         public.approval_decision NOT NULL,
  comment          text,
  decided_at       timestamptz             NOT NULL DEFAULT now(),
  created_at       timestamptz             NOT NULL DEFAULT now(),
  updated_at       timestamptz             NOT NULL DEFAULT now(),
  metadata         jsonb                   DEFAULT '{}'::jsonb
);

CREATE TABLE public.approval_delegations (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid        NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  delegator_id     uuid        NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  delegate_id      uuid        NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  chain_id         uuid        REFERENCES public.approval_chains (id) ON DELETE SET NULL,
  starts_at        timestamptz NOT NULL DEFAULT now(),
  ends_at          timestamptz,
  reason           text,
  is_active        boolean     NOT NULL DEFAULT true,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  metadata         jsonb       DEFAULT '{}'::jsonb
);

-- =============================================================================
-- 3. Indexes
-- =============================================================================

CREATE INDEX idx_approval_chains_org_id      ON public.approval_chains (org_id);
CREATE INDEX idx_approval_chains_entity_type ON public.approval_chains (entity_type);
CREATE INDEX idx_approval_chains_is_active   ON public.approval_chains (is_active) WHERE is_active = true;

CREATE INDEX idx_approval_steps_org_id       ON public.approval_steps (org_id);
CREATE INDEX idx_approval_steps_chain_id     ON public.approval_steps (chain_id);
CREATE INDEX idx_approval_steps_approver_id  ON public.approval_steps (approver_id);

CREATE INDEX idx_approval_requests_org_id       ON public.approval_requests (org_id);
CREATE INDEX idx_approval_requests_chain_id     ON public.approval_requests (chain_id);
CREATE INDEX idx_approval_requests_requester_id ON public.approval_requests (requester_id);
CREATE INDEX idx_approval_requests_status       ON public.approval_requests (status);
CREATE INDEX idx_approval_requests_entity       ON public.approval_requests (entity_type, entity_id);

CREATE INDEX idx_approval_decisions_org_id      ON public.approval_decisions (org_id);
CREATE INDEX idx_approval_decisions_request_id  ON public.approval_decisions (request_id);
CREATE INDEX idx_approval_decisions_decided_by  ON public.approval_decisions (decided_by);

CREATE INDEX idx_approval_delegations_org_id       ON public.approval_delegations (org_id);
CREATE INDEX idx_approval_delegations_delegator_id ON public.approval_delegations (delegator_id);
CREATE INDEX idx_approval_delegations_delegate_id  ON public.approval_delegations (delegate_id);
CREATE INDEX idx_approval_delegations_chain_id     ON public.approval_delegations (chain_id);

-- =============================================================================
-- 4. Triggers
-- =============================================================================

CREATE TRIGGER trg_approval_chains_updated_at BEFORE UPDATE ON public.approval_chains
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_approval_steps_updated_at BEFORE UPDATE ON public.approval_steps
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_approval_requests_updated_at BEFORE UPDATE ON public.approval_requests
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_approval_decisions_updated_at BEFORE UPDATE ON public.approval_decisions
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_approval_delegations_updated_at BEFORE UPDATE ON public.approval_delegations
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- =============================================================================
-- 5. Comments
-- =============================================================================

COMMENT ON TABLE public.approval_chains IS 'Reusable approval workflows tied to an entity type (e.g. expense, contract).';
COMMENT ON COLUMN public.approval_chains.entity_type IS 'The kind of record this chain applies to, such as expense or contract.';
COMMENT ON COLUMN public.approval_chains.is_active IS 'Inactive chains are not used for new requests.';

COMMENT ON TABLE public.approval_steps IS 'Ordered steps within an approval chain. Each step names an approver or a role.';
COMMENT ON COLUMN public.approval_steps.position IS 'Execution order within the chain. Lower values run first.';
COMMENT ON COLUMN public.approval_steps.approver_role IS 'Role-based approver when approver_id is NULL.';
COMMENT ON COLUMN public.approval_steps.is_required IS 'If false, this step may be skipped without blocking approval.';

COMMENT ON TABLE public.approval_requests IS 'A concrete request for approval, linking an entity to a chain.';
COMMENT ON COLUMN public.approval_requests.entity_id IS 'The ID of the record being approved.';
COMMENT ON COLUMN public.approval_requests.resolved_at IS 'Timestamp when the request reached a terminal status.';

COMMENT ON TABLE public.approval_decisions IS 'Individual approve or reject decisions recorded against a request step.';
COMMENT ON COLUMN public.approval_decisions.comment IS 'Optional note explaining the decision.';

COMMENT ON TABLE public.approval_delegations IS 'Temporary delegation of approval authority from one user to another.';
COMMENT ON COLUMN public.approval_delegations.chain_id IS 'NULL means the delegation covers all chains.';
COMMENT ON COLUMN public.approval_delegations.ends_at IS 'NULL means the delegation has no expiration.';

-- =============================================================================
-- 6. Row-Level Security
-- =============================================================================

ALTER TABLE public.approval_chains ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.approval_steps ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.approval_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.approval_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.approval_delegations ENABLE ROW LEVEL SECURITY;

-- approval_chains -------------------------------------------------------------

CREATE POLICY approval_chains_select ON public.approval_chains
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY approval_chains_insert ON public.approval_chains
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY approval_chains_update ON public.approval_chains
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY approval_chains_delete ON public.approval_chains
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- approval_steps --------------------------------------------------------------

CREATE POLICY approval_steps_select ON public.approval_steps
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY approval_steps_insert ON public.approval_steps
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY approval_steps_update ON public.approval_steps
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY approval_steps_delete ON public.approval_steps
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- approval_requests -----------------------------------------------------------

CREATE POLICY approval_requests_select ON public.approval_requests
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY approval_requests_insert ON public.approval_requests
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY approval_requests_update ON public.approval_requests
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY approval_requests_delete ON public.approval_requests
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- approval_decisions ----------------------------------------------------------

CREATE POLICY approval_decisions_select ON public.approval_decisions
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY approval_decisions_insert ON public.approval_decisions
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY approval_decisions_update ON public.approval_decisions
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY approval_decisions_delete ON public.approval_decisions
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- approval_delegations --------------------------------------------------------

CREATE POLICY approval_delegations_select ON public.approval_delegations
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY approval_delegations_insert ON public.approval_delegations
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY approval_delegations_update ON public.approval_delegations
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY approval_delegations_delete ON public.approval_delegations
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());
