-- =============================================================================
-- Skill: compliance
-- Depends on: identity
-- Description: Consent records, deletion requests, and retention policies.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Enums
-- -----------------------------------------------------------------------------
CREATE TYPE public.deletion_status AS ENUM ('requested', 'in_progress', 'completed', 'rejected');
CREATE TYPE public.retention_action AS ENUM ('delete', 'anonymize', 'archive');

-- -----------------------------------------------------------------------------
-- Table: consent_records
-- -----------------------------------------------------------------------------
CREATE TABLE public.consent_records (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  entity_type     text NOT NULL,
  entity_id       uuid NOT NULL,
  purpose         text NOT NULL,
  legal_basis     text NOT NULL,
  granted_at      timestamptz NOT NULL DEFAULT now(),
  revoked_at      timestamptz,
  expires_at      timestamptz,
  ip_address      inet,
  source          text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.consent_records IS 'Records of user or entity consent for data processing purposes.';

CREATE INDEX idx_consent_records_org_id ON public.consent_records(org_id);
CREATE INDEX idx_consent_records_entity_type ON public.consent_records(entity_type);
CREATE INDEX idx_consent_records_entity_id ON public.consent_records(entity_id);
CREATE INDEX idx_consent_records_purpose ON public.consent_records(purpose);

CREATE TRIGGER trg_consent_records_updated_at BEFORE UPDATE ON public.consent_records
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: deletion_requests
-- -----------------------------------------------------------------------------
CREATE TABLE public.deletion_requests (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  requester_type  text NOT NULL,
  requester_id    uuid NOT NULL,
  status          public.deletion_status NOT NULL DEFAULT 'requested',
  reason          text,
  requested_at    timestamptz NOT NULL DEFAULT now(),
  completed_at    timestamptz,
  completed_by    uuid REFERENCES public.users(id) ON DELETE SET NULL,
  notes           text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.deletion_requests IS 'Data deletion requests for GDPR/CCPA right-to-erasure compliance.';

CREATE INDEX idx_deletion_requests_org_id ON public.deletion_requests(org_id);
CREATE INDEX idx_deletion_requests_status ON public.deletion_requests(status);
CREATE INDEX idx_deletion_requests_requester_id ON public.deletion_requests(requester_id);

CREATE TRIGGER trg_deletion_requests_updated_at BEFORE UPDATE ON public.deletion_requests
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: retention_policies
-- -----------------------------------------------------------------------------
CREATE TABLE public.retention_policies (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  entity_type     text NOT NULL,
  retention_days  integer NOT NULL,
  action          public.retention_action NOT NULL DEFAULT 'archive',
  is_active       boolean NOT NULL DEFAULT true,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb,
  UNIQUE (org_id, entity_type)
);

COMMENT ON TABLE public.retention_policies IS 'Data retention policies defining how long entities are kept and what action to take on expiry.';

CREATE INDEX idx_retention_policies_org_id ON public.retention_policies(org_id);
CREATE INDEX idx_retention_policies_entity_type ON public.retention_policies(entity_type);
CREATE INDEX idx_retention_policies_is_active ON public.retention_policies(is_active);

CREATE TRIGGER trg_retention_policies_updated_at BEFORE UPDATE ON public.retention_policies
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- RLS
-- -----------------------------------------------------------------------------

-- consent_records
ALTER TABLE public.consent_records ENABLE ROW LEVEL SECURITY;

CREATE POLICY "consent_records_select" ON public.consent_records
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "consent_records_insert" ON public.consent_records
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "consent_records_update" ON public.consent_records
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "consent_records_delete" ON public.consent_records
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- deletion_requests
ALTER TABLE public.deletion_requests ENABLE ROW LEVEL SECURITY;

CREATE POLICY "deletion_requests_select" ON public.deletion_requests
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "deletion_requests_insert" ON public.deletion_requests
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "deletion_requests_update" ON public.deletion_requests
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "deletion_requests_delete" ON public.deletion_requests
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- retention_policies
ALTER TABLE public.retention_policies ENABLE ROW LEVEL SECURITY;

CREATE POLICY "retention_policies_select" ON public.retention_policies
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "retention_policies_insert" ON public.retention_policies
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "retention_policies_update" ON public.retention_policies
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "retention_policies_delete" ON public.retention_policies
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());
