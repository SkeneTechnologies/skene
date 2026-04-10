-- =============================================================================
-- Migration: 00005_support
-- Description: Support tickets. Also defines channel_type enum shared with comms.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Enums
-- -----------------------------------------------------------------------------
CREATE TYPE public.ticket_status AS ENUM ('open', 'pending', 'resolved', 'closed');
CREATE TYPE public.ticket_priority AS ENUM ('low', 'medium', 'high', 'urgent');
CREATE TYPE public.channel_type AS ENUM ('email', 'sms', 'chat', 'phone', 'social');

-- -----------------------------------------------------------------------------
-- Table: tickets
-- Support requests from contacts or internal users.
-- -----------------------------------------------------------------------------
CREATE TABLE public.tickets (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  contact_id      uuid REFERENCES public.contacts(id) ON DELETE SET NULL,
  assignee_id     uuid REFERENCES public.users(id) ON DELETE SET NULL,
  creator_id      uuid REFERENCES public.users(id) ON DELETE SET NULL,
  title           text NOT NULL,
  description     text,
  status          public.ticket_status NOT NULL DEFAULT 'open',
  priority        public.ticket_priority NOT NULL DEFAULT 'medium',
  channel         public.channel_type,
  resolved_at     timestamptz,
  closed_at       timestamptz,
  first_response_at timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.tickets IS 'Support requests. Tracks status, priority, SLA timestamps.';
COMMENT ON COLUMN public.tickets.channel IS 'The channel through which this ticket was created.';
COMMENT ON COLUMN public.tickets.first_response_at IS 'When the first agent response was sent. Used for SLA tracking.';

CREATE INDEX idx_tickets_org_id ON public.tickets(org_id);
CREATE INDEX idx_tickets_contact_id ON public.tickets(contact_id);
CREATE INDEX idx_tickets_assignee_id ON public.tickets(assignee_id);
CREATE INDEX idx_tickets_status ON public.tickets(status);
CREATE INDEX idx_tickets_priority ON public.tickets(priority);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.tickets
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
