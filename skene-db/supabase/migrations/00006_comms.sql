-- =============================================================================
-- Migration: 00006_comms
-- Description: Threads and messages. Polymorphic threads can attach to any entity.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Enums
-- -----------------------------------------------------------------------------
CREATE TYPE public.message_direction AS ENUM ('inbound', 'outbound', 'internal');

-- -----------------------------------------------------------------------------
-- Table: threads
-- A conversation thread attached to any entity (contact, deal, ticket, etc).
-- -----------------------------------------------------------------------------
CREATE TABLE public.threads (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  entity_type     text NOT NULL,
  entity_id       uuid NOT NULL,
  subject         text,
  channel         public.channel_type,
  is_closed       boolean NOT NULL DEFAULT false,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb,
  CHECK (entity_type IN ('contact', 'company', 'deal', 'ticket', 'task', 'project'))
);

COMMENT ON TABLE public.threads IS 'Conversation threads. Polymorphic: attaches to any entity via entity_type + entity_id.';
COMMENT ON COLUMN public.threads.entity_type IS 'The type of entity this thread is about (contact, deal, ticket, etc).';
COMMENT ON COLUMN public.threads.entity_id IS 'The UUID of the entity this thread is about. No FK constraint (polymorphic).';

CREATE INDEX idx_threads_org_id ON public.threads(org_id);
CREATE INDEX idx_threads_entity ON public.threads(entity_type, entity_id);
CREATE INDEX idx_threads_channel ON public.threads(channel);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.threads
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: messages
-- Individual messages within a thread.
-- -----------------------------------------------------------------------------
CREATE TABLE public.messages (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  thread_id       uuid NOT NULL REFERENCES public.threads(id) ON DELETE CASCADE,
  author_id       uuid REFERENCES public.users(id) ON DELETE SET NULL,
  contact_id      uuid REFERENCES public.contacts(id) ON DELETE SET NULL,
  direction       public.message_direction NOT NULL DEFAULT 'internal',
  body            text NOT NULL,
  html_body       text,
  external_id     text,
  sent_at         timestamptz DEFAULT now(),
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.messages IS 'Individual messages within a thread. Can be from a user or a contact.';
COMMENT ON COLUMN public.messages.direction IS 'Whether the message is inbound (from contact), outbound (to contact), or internal.';
COMMENT ON COLUMN public.messages.external_id IS 'ID from the external system (e.g. email Message-ID, SMS SID).';
COMMENT ON COLUMN public.messages.html_body IS 'Rich HTML version of the message body.';

CREATE INDEX idx_messages_org_id ON public.messages(org_id);
CREATE INDEX idx_messages_thread_id ON public.messages(thread_id);
CREATE INDEX idx_messages_author_id ON public.messages(author_id);
CREATE INDEX idx_messages_contact_id ON public.messages(contact_id);
CREATE INDEX idx_messages_sent_at ON public.messages(sent_at);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.messages
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
