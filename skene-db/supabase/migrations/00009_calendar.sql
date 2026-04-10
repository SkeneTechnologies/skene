-- =============================================================================
-- Migration: 00009_calendar
-- Description: Events and event attendees.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Enums
-- -----------------------------------------------------------------------------
CREATE TYPE public.event_status AS ENUM ('confirmed', 'tentative', 'cancelled');
CREATE TYPE public.attendee_response AS ENUM ('accepted', 'declined', 'tentative', 'pending');

-- -----------------------------------------------------------------------------
-- Table: events
-- Calendar events. Polymorphic: can relate to any entity.
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

COMMENT ON TABLE public.events IS 'Calendar events. Optionally linked to an entity (deal, contact, etc).';
COMMENT ON COLUMN public.events.recurrence_rule IS 'iCal RRULE string for recurring events (e.g. FREQ=WEEKLY;BYDAY=MO).';
COMMENT ON COLUMN public.events.entity_type IS 'Optional polymorphic link to a related entity.';

CREATE INDEX idx_events_org_id ON public.events(org_id);
CREATE INDEX idx_events_creator_id ON public.events(creator_id);
CREATE INDEX idx_events_starts_at ON public.events(starts_at);
CREATE INDEX idx_events_entity ON public.events(entity_type, entity_id) WHERE entity_type IS NOT NULL;
CREATE INDEX idx_events_status ON public.events(status);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.events
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: event_attendees
-- People attending an event. Can be users or contacts.
-- -----------------------------------------------------------------------------
CREATE TABLE public.event_attendees (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  event_id        uuid NOT NULL REFERENCES public.events(id) ON DELETE CASCADE,
  user_id         uuid REFERENCES public.users(id) ON DELETE CASCADE,
  contact_id      uuid REFERENCES public.contacts(id) ON DELETE CASCADE,
  response        public.attendee_response NOT NULL DEFAULT 'pending',
  is_organizer    boolean NOT NULL DEFAULT false,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb,
  CHECK (user_id IS NOT NULL OR contact_id IS NOT NULL)
);

COMMENT ON TABLE public.event_attendees IS 'Event participants. Either a user or a contact (at least one must be set).';

CREATE INDEX idx_event_attendees_org_id ON public.event_attendees(org_id);
CREATE INDEX idx_event_attendees_event_id ON public.event_attendees(event_id);
CREATE INDEX idx_event_attendees_user_id ON public.event_attendees(user_id);
CREATE INDEX idx_event_attendees_contact_id ON public.event_attendees(contact_id);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.event_attendees
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
