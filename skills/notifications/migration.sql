-- notifications skill: templates, deliveries, preferences, and push tokens
-- Depends on identity for organizations and users.

-- =============================================================================
-- 1. Enums
-- =============================================================================

CREATE TYPE public.notification_channel AS ENUM ('email', 'sms', 'push', 'in_app');
CREATE TYPE public.delivery_status AS ENUM ('queued', 'sent', 'delivered', 'failed', 'read');
CREATE TYPE public.push_platform AS ENUM ('ios', 'android', 'web');

-- =============================================================================
-- 2. Tables
-- =============================================================================

CREATE TABLE public.notification_templates (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid        NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  name             text        NOT NULL,
  slug             text        NOT NULL,
  channel          public.notification_channel NOT NULL,
  subject          text,
  body_template    text        NOT NULL,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  metadata         jsonb       DEFAULT '{}'::jsonb,
  UNIQUE (org_id, slug)
);

CREATE TABLE public.notification_deliveries (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid        NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  template_id      uuid        REFERENCES public.notification_templates (id) ON DELETE SET NULL,
  user_id          uuid        NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  channel          public.notification_channel NOT NULL,
  subject          text,
  body             text        NOT NULL,
  status           public.delivery_status NOT NULL DEFAULT 'queued',
  sent_at          timestamptz,
  read_at          timestamptz,
  error            text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  metadata         jsonb       DEFAULT '{}'::jsonb
);

CREATE TABLE public.notification_preferences (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid        NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  user_id          uuid        NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  channel          public.notification_channel NOT NULL,
  category         text        NOT NULL DEFAULT 'general',
  is_enabled       boolean     NOT NULL DEFAULT true,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  metadata         jsonb       DEFAULT '{}'::jsonb,
  UNIQUE (user_id, channel, category)
);

CREATE TABLE public.push_tokens (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid        NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  user_id          uuid        NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  token            text        NOT NULL,
  platform         public.push_platform NOT NULL,
  device_name      text,
  is_active        boolean     NOT NULL DEFAULT true,
  last_used_at     timestamptz,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  metadata         jsonb       DEFAULT '{}'::jsonb,
  UNIQUE (user_id, token)
);

-- =============================================================================
-- 3. Indexes
-- =============================================================================

CREATE INDEX idx_notification_templates_org_id   ON public.notification_templates (org_id);
CREATE INDEX idx_notification_templates_channel  ON public.notification_templates (channel);
CREATE INDEX idx_notification_templates_slug     ON public.notification_templates (slug);
CREATE INDEX idx_notification_deliveries_org_id  ON public.notification_deliveries (org_id);
CREATE INDEX idx_notification_deliveries_user_id ON public.notification_deliveries (user_id);
CREATE INDEX idx_notification_deliveries_status  ON public.notification_deliveries (status);
CREATE INDEX idx_notification_deliveries_channel ON public.notification_deliveries (channel);
CREATE INDEX idx_notification_preferences_org_id ON public.notification_preferences (org_id);
CREATE INDEX idx_notification_preferences_user_id ON public.notification_preferences (user_id);
CREATE INDEX idx_push_tokens_org_id              ON public.push_tokens (org_id);
CREATE INDEX idx_push_tokens_user_id             ON public.push_tokens (user_id);
CREATE INDEX idx_push_tokens_platform            ON public.push_tokens (platform);

-- =============================================================================
-- 4. Triggers
-- =============================================================================

CREATE TRIGGER trg_notification_templates_updated_at BEFORE UPDATE ON public.notification_templates
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_notification_deliveries_updated_at BEFORE UPDATE ON public.notification_deliveries
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_notification_preferences_updated_at BEFORE UPDATE ON public.notification_preferences
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_push_tokens_updated_at BEFORE UPDATE ON public.push_tokens
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- =============================================================================
-- 5. Comments
-- =============================================================================

COMMENT ON TABLE public.notification_templates IS 'Reusable notification template with channel, subject, and body. Scoped to an org.';
COMMENT ON TABLE public.notification_deliveries IS 'Individual notification sent to a user. Tracks delivery lifecycle from queued to read.';
COMMENT ON TABLE public.notification_preferences IS 'Per-user opt-in/opt-out preference for a channel and category combination.';
COMMENT ON TABLE public.push_tokens IS 'Device push token registered by a user. Supports iOS, Android, and web push.';

COMMENT ON COLUMN public.notification_templates.slug IS 'URL-safe identifier, unique per org. Used to look up templates in code.';
COMMENT ON COLUMN public.notification_templates.body_template IS 'Template string with placeholder variables, e.g. "Hello {{name}}, your order {{order_id}} shipped."';
COMMENT ON COLUMN public.notification_deliveries.status IS 'Lifecycle state: queued, sent, delivered, failed, or read.';
COMMENT ON COLUMN public.notification_deliveries.error IS 'Error message if delivery failed. NULL on success.';
COMMENT ON COLUMN public.notification_preferences.category IS 'Notification category, e.g. "marketing", "billing", "general". Defaults to general.';
COMMENT ON COLUMN public.push_tokens.is_active IS 'Set to false when the token is expired or revoked. Inactive tokens are skipped during delivery.';
COMMENT ON COLUMN public.push_tokens.last_used_at IS 'Timestamp of last successful push delivery using this token.';

-- =============================================================================
-- 6. Row-Level Security
-- =============================================================================

ALTER TABLE public.notification_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notification_deliveries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notification_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.push_tokens ENABLE ROW LEVEL SECURITY;

-- notification_templates ---------------------------------------------------------

CREATE POLICY notification_templates_select ON public.notification_templates
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY notification_templates_insert ON public.notification_templates
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY notification_templates_update ON public.notification_templates
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY notification_templates_delete ON public.notification_templates
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- notification_deliveries --------------------------------------------------------

CREATE POLICY notification_deliveries_select ON public.notification_deliveries
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY notification_deliveries_insert ON public.notification_deliveries
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY notification_deliveries_update ON public.notification_deliveries
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY notification_deliveries_delete ON public.notification_deliveries
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- notification_preferences -------------------------------------------------------

CREATE POLICY notification_preferences_select ON public.notification_preferences
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY notification_preferences_insert ON public.notification_preferences
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY notification_preferences_update ON public.notification_preferences
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY notification_preferences_delete ON public.notification_preferences
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- push_tokens --------------------------------------------------------------------

CREATE POLICY push_tokens_select ON public.push_tokens
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY push_tokens_insert ON public.push_tokens
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY push_tokens_update ON public.push_tokens
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY push_tokens_delete ON public.push_tokens
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());
