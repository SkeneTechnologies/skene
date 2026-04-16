-- comms skill: threads, messages
-- Depends on crm.

-- =============================================================================
-- 1. Enums
-- =============================================================================

CREATE TYPE public.message_direction AS ENUM ('inbound', 'outbound', 'internal');

-- channel_type may already exist from the support skill
DO $$ BEGIN
  CREATE TYPE public.channel_type AS ENUM ('email', 'sms', 'chat', 'phone', 'social');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

-- =============================================================================
-- 2. Tables
-- =============================================================================

CREATE TABLE public.threads (
  id               uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid          NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  entity_type      text          NOT NULL,
  entity_id        uuid          NOT NULL,
  subject          text,
  channel          public.channel_type,
  is_closed        boolean       NOT NULL DEFAULT false,
  created_at       timestamptz   NOT NULL DEFAULT now(),
  updated_at       timestamptz   NOT NULL DEFAULT now(),
  metadata         jsonb         DEFAULT '{}'::jsonb,
  CHECK (entity_type IN ('contact', 'company', 'deal', 'ticket', 'task', 'project'))
);

CREATE TABLE public.messages (
  id               uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid          NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  thread_id        uuid          NOT NULL REFERENCES public.threads (id) ON DELETE CASCADE,
  author_id        uuid          REFERENCES public.users (id) ON DELETE SET NULL,
  contact_id       uuid          REFERENCES public.contacts (id) ON DELETE SET NULL,
  direction        public.message_direction NOT NULL DEFAULT 'internal',
  body             text          NOT NULL,
  html_body        text,
  external_id      text,
  sent_at          timestamptz   DEFAULT now(),
  created_at       timestamptz   NOT NULL DEFAULT now(),
  updated_at       timestamptz   NOT NULL DEFAULT now(),
  metadata         jsonb         DEFAULT '{}'::jsonb
);

-- =============================================================================
-- 3. Indexes
-- =============================================================================

CREATE INDEX idx_threads_org_id    ON public.threads (org_id);
CREATE INDEX idx_threads_entity    ON public.threads (entity_type, entity_id);
CREATE INDEX idx_threads_channel   ON public.threads (channel);

CREATE INDEX idx_messages_org_id      ON public.messages (org_id);
CREATE INDEX idx_messages_thread_id   ON public.messages (thread_id);
CREATE INDEX idx_messages_author_id   ON public.messages (author_id);
CREATE INDEX idx_messages_contact_id  ON public.messages (contact_id);
CREATE INDEX idx_messages_sent_at     ON public.messages (sent_at);

-- =============================================================================
-- 4. Triggers
-- =============================================================================

CREATE TRIGGER trg_threads_updated_at BEFORE UPDATE ON public.threads
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_messages_updated_at BEFORE UPDATE ON public.messages
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- =============================================================================
-- 5. Comments
-- =============================================================================

COMMENT ON TABLE public.threads IS 'Polymorphic conversation threads attached to any entity.';
COMMENT ON TABLE public.messages IS 'Individual messages within a thread.';

COMMENT ON COLUMN public.threads.entity_type IS 'What this thread attaches to. No FK enforced for polymorphism.';
COMMENT ON COLUMN public.threads.entity_id IS 'ID of the related entity. No FK enforced for polymorphism.';
COMMENT ON COLUMN public.messages.direction IS 'Whether the message is inbound, outbound, or internal.';
COMMENT ON COLUMN public.messages.external_id IS 'ID from external system, e.g. email Message-ID.';
COMMENT ON COLUMN public.messages.html_body IS 'Rich HTML version of the message body.';

-- =============================================================================
-- 6. Row-Level Security
-- =============================================================================

ALTER TABLE public.threads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;

-- threads ---------------------------------------------------------------------

CREATE POLICY threads_select ON public.threads
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY threads_insert ON public.threads
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY threads_update ON public.threads
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY threads_delete ON public.threads
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- messages --------------------------------------------------------------------

CREATE POLICY messages_select ON public.messages
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY messages_insert ON public.messages
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY messages_update ON public.messages
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY messages_delete ON public.messages
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());
