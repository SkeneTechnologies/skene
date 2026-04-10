-- =============================================================================
-- Skill: calendar
-- Depends on: identity
-- Description: Events and attendees with optional polymorphic entity links.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Enums
-- -----------------------------------------------------------------------------
CREATE TYPE public.event_status AS ENUM ('confirmed', 'tentative', 'cancelled');
CREATE TYPE public.attendee_response AS ENUM ('accepted', 'declined', 'tentative', 'pending');

-- -----------------------------------------------------------------------------
-- Table: events
-- -----------------------------------------------------------------------------
CREATE TABLE public.events (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  creator_id      uuid REFERENCES public.users(id) ON DELETE SET NULL,
  entity_type     text,
  entity_id       uuid,
  title           text NOT NULL,
  description     text,
  location        text,
  status          public.event_status NOT NULL DEFAULT 'confirmed',
  starts_at       timestamptz NOT NULL,
  ends_at         timestamptz NOT NULL,
  all_day         boolean NOT NULL DEFAULT false,
  recurrence_rule text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb,
  CHECK (entity_type IS NULL OR entity_type IN ('contact', 'company', 'deal', 'ticket', 'project'))
);

COMMENT ON COLUMN public.events.entity_type IS 'Optional polymorphic link to a related record.';
COMMENT ON COLUMN public.events.recurrence_rule IS 'iCal RRULE string.';

CREATE INDEX idx_events_org_id ON public.events(org_id);
CREATE INDEX idx_events_creator_id ON public.events(creator_id);
CREATE INDEX idx_events_starts_at ON public.events(starts_at);
CREATE INDEX idx_events_entity ON public.events(entity_type, entity_id) WHERE entity_type IS NOT NULL;
CREATE INDEX idx_events_status ON public.events(status);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.events
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: event_attendees
-- At least one of user_id or contact_id is required.
-- contact_id has no FK so calendar works without the CRM skill installed.
-- -----------------------------------------------------------------------------
CREATE TABLE public.event_attendees (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  event_id        uuid NOT NULL REFERENCES public.events(id) ON DELETE CASCADE,
  user_id         uuid REFERENCES public.users(id) ON DELETE CASCADE,
  contact_id      uuid,
  response        public.attendee_response NOT NULL DEFAULT 'pending',
  is_organizer    boolean NOT NULL DEFAULT false,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb,
  CHECK (user_id IS NOT NULL OR contact_id IS NOT NULL)
);

COMMENT ON TABLE public.event_attendees IS 'At least one of user_id or contact_id required.';
COMMENT ON COLUMN public.event_attendees.contact_id IS 'References contacts table if CRM skill is installed. No FK constraint.';

CREATE INDEX idx_event_attendees_org_id ON public.event_attendees(org_id);
CREATE INDEX idx_event_attendees_event_id ON public.event_attendees(event_id);
CREATE INDEX idx_event_attendees_user_id ON public.event_attendees(user_id);
CREATE INDEX idx_event_attendees_contact_id ON public.event_attendees(contact_id);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.event_attendees
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- RLS
-- -----------------------------------------------------------------------------

-- events
ALTER TABLE public.events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "events_select" ON public.events
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "events_insert" ON public.events
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "events_update" ON public.events
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "events_delete" ON public.events
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- event_attendees
ALTER TABLE public.event_attendees ENABLE ROW LEVEL SECURITY;

CREATE POLICY "event_attendees_select" ON public.event_attendees
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "event_attendees_insert" ON public.event_attendees
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "event_attendees_update" ON public.event_attendees
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "event_attendees_delete" ON public.event_attendees
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());
