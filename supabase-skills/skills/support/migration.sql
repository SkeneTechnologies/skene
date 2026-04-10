-- support skill: tickets
-- Depends on crm.

-- =============================================================================
-- 1. Enums
-- =============================================================================

CREATE TYPE public.ticket_status AS ENUM ('open', 'pending', 'resolved', 'closed');
CREATE TYPE public.ticket_priority AS ENUM ('low', 'medium', 'high', 'urgent');
CREATE TYPE public.channel_type AS ENUM ('email', 'sms', 'chat', 'phone', 'social');

-- =============================================================================
-- 2. Tables
-- =============================================================================

CREATE TABLE public.tickets (
  id                uuid             PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id            uuid             NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  contact_id        uuid             REFERENCES public.contacts (id) ON DELETE SET NULL,
  assignee_id       uuid             REFERENCES public.users (id) ON DELETE SET NULL,
  creator_id        uuid             REFERENCES public.users (id) ON DELETE SET NULL,
  title             text             NOT NULL,
  description       text,
  status            public.ticket_status   NOT NULL DEFAULT 'open',
  priority          public.ticket_priority NOT NULL DEFAULT 'medium',
  channel           public.channel_type,
  resolved_at       timestamptz,
  closed_at         timestamptz,
  first_response_at timestamptz,
  created_at        timestamptz      NOT NULL DEFAULT now(),
  updated_at        timestamptz      NOT NULL DEFAULT now(),
  metadata          jsonb            DEFAULT '{}'::jsonb
);

-- =============================================================================
-- 3. Indexes
-- =============================================================================

CREATE INDEX idx_tickets_org_id      ON public.tickets (org_id);
CREATE INDEX idx_tickets_contact_id  ON public.tickets (contact_id);
CREATE INDEX idx_tickets_assignee_id ON public.tickets (assignee_id);
CREATE INDEX idx_tickets_status      ON public.tickets (status);
CREATE INDEX idx_tickets_priority    ON public.tickets (priority);

-- =============================================================================
-- 4. Triggers
-- =============================================================================

CREATE TRIGGER trg_tickets_updated_at BEFORE UPDATE ON public.tickets
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- =============================================================================
-- 5. Comments
-- =============================================================================

COMMENT ON TABLE public.tickets IS 'Support requests linked to contacts.';

COMMENT ON COLUMN public.tickets.channel IS 'How the ticket was created.';
COMMENT ON COLUMN public.tickets.first_response_at IS 'For SLA tracking.';

-- =============================================================================
-- 6. Row-Level Security
-- =============================================================================

ALTER TABLE public.tickets ENABLE ROW LEVEL SECURITY;

-- tickets ---------------------------------------------------------------------

CREATE POLICY tickets_select ON public.tickets
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY tickets_insert ON public.tickets
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY tickets_update ON public.tickets
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY tickets_delete ON public.tickets
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());
