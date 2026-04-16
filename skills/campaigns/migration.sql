-- campaigns skill: campaigns, segments, lists, sends, and engagement events
-- Depends on crm (contacts).

-- =============================================================================
-- 1. Enums
-- =============================================================================

CREATE TYPE public.campaign_status AS ENUM ('draft', 'scheduled', 'sending', 'sent', 'paused', 'canceled');
CREATE TYPE public.send_status AS ENUM ('queued', 'sent', 'delivered', 'bounced', 'failed');
CREATE TYPE public.campaign_event_type AS ENUM ('open', 'click', 'unsubscribe', 'complaint', 'bounce');

-- =============================================================================
-- 2. Tables
-- =============================================================================

CREATE TABLE public.campaigns (
  id            uuid                   PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid                   NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  creator_id    uuid                   REFERENCES public.users (id) ON DELETE SET NULL,
  name          text                   NOT NULL,
  subject       text,
  body          text,
  channel       text                   NOT NULL DEFAULT 'email',
  status        public.campaign_status NOT NULL DEFAULT 'draft',
  scheduled_at  timestamptz,
  sent_at       timestamptz,
  created_at    timestamptz            NOT NULL DEFAULT now(),
  updated_at    timestamptz            NOT NULL DEFAULT now(),
  metadata      jsonb                  DEFAULT '{}'::jsonb
);

CREATE TABLE public.campaign_segments (
  id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id         uuid        NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  name           text        NOT NULL,
  description    text,
  filter_rules   jsonb       NOT NULL DEFAULT '{}'::jsonb,
  contact_count  integer     DEFAULT 0,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  metadata       jsonb       DEFAULT '{}'::jsonb
);

CREATE TABLE public.campaign_lists (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid        NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  campaign_id uuid        NOT NULL REFERENCES public.campaigns (id) ON DELETE CASCADE,
  segment_id  uuid        REFERENCES public.campaign_segments (id) ON DELETE SET NULL,
  contact_id  uuid        NOT NULL REFERENCES public.contacts (id) ON DELETE CASCADE,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  metadata    jsonb       DEFAULT '{}'::jsonb,
  UNIQUE (campaign_id, contact_id)
);

CREATE TABLE public.campaign_sends (
  id            uuid              PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid              NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  campaign_id   uuid              NOT NULL REFERENCES public.campaigns (id) ON DELETE CASCADE,
  contact_id    uuid              NOT NULL REFERENCES public.contacts (id) ON DELETE CASCADE,
  status        public.send_status NOT NULL DEFAULT 'queued',
  sent_at       timestamptz,
  delivered_at  timestamptz,
  error         text,
  created_at    timestamptz       NOT NULL DEFAULT now(),
  updated_at    timestamptz       NOT NULL DEFAULT now(),
  metadata      jsonb             DEFAULT '{}'::jsonb
);

CREATE TABLE public.campaign_events (
  id          uuid                       PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid                       NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  send_id     uuid                       NOT NULL REFERENCES public.campaign_sends (id) ON DELETE CASCADE,
  event_type  public.campaign_event_type NOT NULL,
  url         text,
  occurred_at timestamptz                NOT NULL DEFAULT now(),
  created_at  timestamptz                NOT NULL DEFAULT now(),
  updated_at  timestamptz                NOT NULL DEFAULT now(),
  metadata    jsonb                      DEFAULT '{}'::jsonb
);

-- =============================================================================
-- 3. Indexes
-- =============================================================================

CREATE INDEX idx_campaigns_org_id      ON public.campaigns (org_id);
CREATE INDEX idx_campaigns_creator_id  ON public.campaigns (creator_id);
CREATE INDEX idx_campaigns_status      ON public.campaigns (status);

CREATE INDEX idx_campaign_segments_org_id ON public.campaign_segments (org_id);

CREATE INDEX idx_campaign_lists_org_id      ON public.campaign_lists (org_id);
CREATE INDEX idx_campaign_lists_campaign_id ON public.campaign_lists (campaign_id);
CREATE INDEX idx_campaign_lists_segment_id  ON public.campaign_lists (segment_id);
CREATE INDEX idx_campaign_lists_contact_id  ON public.campaign_lists (contact_id);

CREATE INDEX idx_campaign_sends_org_id      ON public.campaign_sends (org_id);
CREATE INDEX idx_campaign_sends_campaign_id ON public.campaign_sends (campaign_id);
CREATE INDEX idx_campaign_sends_contact_id  ON public.campaign_sends (contact_id);
CREATE INDEX idx_campaign_sends_status      ON public.campaign_sends (status);

CREATE INDEX idx_campaign_events_org_id     ON public.campaign_events (org_id);
CREATE INDEX idx_campaign_events_send_id    ON public.campaign_events (send_id);
CREATE INDEX idx_campaign_events_event_type ON public.campaign_events (event_type);

-- =============================================================================
-- 4. Triggers
-- =============================================================================

CREATE TRIGGER trg_campaigns_updated_at BEFORE UPDATE ON public.campaigns
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_campaign_segments_updated_at BEFORE UPDATE ON public.campaign_segments
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_campaign_lists_updated_at BEFORE UPDATE ON public.campaign_lists
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_campaign_sends_updated_at BEFORE UPDATE ON public.campaign_sends
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_campaign_events_updated_at BEFORE UPDATE ON public.campaign_events
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- =============================================================================
-- 5. Comments
-- =============================================================================

COMMENT ON TABLE public.campaigns IS 'Marketing campaigns sent via email or other channels.';
COMMENT ON TABLE public.campaign_segments IS 'Audience segments defined by filter rules for targeting contacts.';
COMMENT ON TABLE public.campaign_lists IS 'Mapping of contacts to campaigns, optionally via a segment.';
COMMENT ON TABLE public.campaign_sends IS 'Individual send records tracking delivery status per contact.';
COMMENT ON TABLE public.campaign_events IS 'Engagement events (opens, clicks, bounces) tied to sends.';

COMMENT ON COLUMN public.campaigns.channel IS 'Delivery channel: email, sms, push, etc.';
COMMENT ON COLUMN public.campaign_segments.filter_rules IS 'JSON filter criteria used to resolve matching contacts.';
COMMENT ON COLUMN public.campaign_segments.contact_count IS 'Cached count of contacts matching the segment.';
COMMENT ON COLUMN public.campaign_sends.error IS 'Error message if delivery failed.';
COMMENT ON COLUMN public.campaign_events.url IS 'Clicked URL for click events. NULL for other event types.';
COMMENT ON COLUMN public.campaign_events.occurred_at IS 'Timestamp when the engagement event occurred.';

-- =============================================================================
-- 6. Row-Level Security
-- =============================================================================

ALTER TABLE public.campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.campaign_segments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.campaign_lists ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.campaign_sends ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.campaign_events ENABLE ROW LEVEL SECURITY;

-- campaigns -------------------------------------------------------------------

CREATE POLICY campaigns_select ON public.campaigns
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY campaigns_insert ON public.campaigns
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY campaigns_update ON public.campaigns
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY campaigns_delete ON public.campaigns
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- campaign_segments -----------------------------------------------------------

CREATE POLICY campaign_segments_select ON public.campaign_segments
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY campaign_segments_insert ON public.campaign_segments
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY campaign_segments_update ON public.campaign_segments
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY campaign_segments_delete ON public.campaign_segments
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- campaign_lists --------------------------------------------------------------

CREATE POLICY campaign_lists_select ON public.campaign_lists
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY campaign_lists_insert ON public.campaign_lists
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY campaign_lists_update ON public.campaign_lists
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY campaign_lists_delete ON public.campaign_lists
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- campaign_sends --------------------------------------------------------------

CREATE POLICY campaign_sends_select ON public.campaign_sends
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY campaign_sends_insert ON public.campaign_sends
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY campaign_sends_update ON public.campaign_sends
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY campaign_sends_delete ON public.campaign_sends
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- campaign_events -------------------------------------------------------------

CREATE POLICY campaign_events_select ON public.campaign_events
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY campaign_events_insert ON public.campaign_events
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY campaign_events_update ON public.campaign_events
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY campaign_events_delete ON public.campaign_events
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());
