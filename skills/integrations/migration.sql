-- =============================================================================
-- Skill: integrations
-- Depends on: identity
-- Description: Connected apps, OAuth tokens, webhooks, and sync logs.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Enums
-- -----------------------------------------------------------------------------
CREATE TYPE public.integration_status AS ENUM ('active', 'inactive', 'error');
CREATE TYPE public.webhook_event_status AS ENUM ('pending', 'sent', 'failed');
CREATE TYPE public.sync_direction AS ENUM ('inbound', 'outbound');
CREATE TYPE public.sync_status AS ENUM ('pending', 'running', 'completed', 'failed');

-- -----------------------------------------------------------------------------
-- Table: connected_apps
-- -----------------------------------------------------------------------------
CREATE TABLE public.connected_apps (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  name            text NOT NULL,
  provider        text NOT NULL,
  status          public.integration_status NOT NULL DEFAULT 'active',
  config          jsonb DEFAULT '{}'::jsonb,
  connected_by    uuid REFERENCES public.users(id) ON DELETE SET NULL,
  connected_at    timestamptz NOT NULL DEFAULT now(),
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.connected_apps IS 'Third-party applications connected to an organization.';

CREATE INDEX idx_connected_apps_org_id ON public.connected_apps(org_id);
CREATE INDEX idx_connected_apps_provider ON public.connected_apps(provider);
CREATE INDEX idx_connected_apps_status ON public.connected_apps(status);

CREATE TRIGGER trg_connected_apps_updated_at BEFORE UPDATE ON public.connected_apps
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: oauth_tokens
-- Tokens stored encrypted; decryption happens in the application layer.
-- -----------------------------------------------------------------------------
CREATE TABLE public.oauth_tokens (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id            uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  app_id            uuid NOT NULL REFERENCES public.connected_apps(id) ON DELETE CASCADE,
  user_id           uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  access_token_enc  text NOT NULL,
  refresh_token_enc text,
  token_type        text DEFAULT 'bearer',
  scopes            text[],
  expires_at        timestamptz,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),
  metadata          jsonb DEFAULT '{}'::jsonb,
  UNIQUE (app_id, user_id)
);

COMMENT ON TABLE public.oauth_tokens IS 'OAuth tokens stored encrypted; decryption happens in the application layer.';

CREATE INDEX idx_oauth_tokens_org_id ON public.oauth_tokens(org_id);
CREATE INDEX idx_oauth_tokens_app_id ON public.oauth_tokens(app_id);
CREATE INDEX idx_oauth_tokens_user_id ON public.oauth_tokens(user_id);

CREATE TRIGGER trg_oauth_tokens_updated_at BEFORE UPDATE ON public.oauth_tokens
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: webhooks
-- -----------------------------------------------------------------------------
CREATE TABLE public.webhooks (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  url             text NOT NULL,
  secret          text,
  events          text[] NOT NULL,
  is_active       boolean NOT NULL DEFAULT true,
  created_by      uuid REFERENCES public.users(id) ON DELETE SET NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.webhooks IS 'Outgoing webhook endpoints registered by an organization.';

CREATE INDEX idx_webhooks_org_id ON public.webhooks(org_id);
CREATE INDEX idx_webhooks_is_active ON public.webhooks(is_active);

CREATE TRIGGER trg_webhooks_updated_at BEFORE UPDATE ON public.webhooks
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: webhook_events
-- -----------------------------------------------------------------------------
CREATE TABLE public.webhook_events (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  webhook_id      uuid NOT NULL REFERENCES public.webhooks(id) ON DELETE CASCADE,
  event_type      text NOT NULL,
  payload         jsonb NOT NULL,
  status          public.webhook_event_status NOT NULL DEFAULT 'pending',
  response_code   smallint,
  attempts        integer NOT NULL DEFAULT 0,
  last_attempt_at timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.webhook_events IS 'Individual delivery attempts for outgoing webhook events.';

CREATE INDEX idx_webhook_events_org_id ON public.webhook_events(org_id);
CREATE INDEX idx_webhook_events_webhook_id ON public.webhook_events(webhook_id);
CREATE INDEX idx_webhook_events_status ON public.webhook_events(status);
CREATE INDEX idx_webhook_events_event_type ON public.webhook_events(event_type);

CREATE TRIGGER trg_webhook_events_updated_at BEFORE UPDATE ON public.webhook_events
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: sync_logs
-- -----------------------------------------------------------------------------
CREATE TABLE public.sync_logs (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id              uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  app_id              uuid NOT NULL REFERENCES public.connected_apps(id) ON DELETE CASCADE,
  direction           public.sync_direction NOT NULL,
  entity_type         text NOT NULL,
  entity_id           uuid,
  status              public.sync_status NOT NULL DEFAULT 'pending',
  records_processed   integer DEFAULT 0,
  records_failed      integer DEFAULT 0,
  started_at          timestamptz,
  completed_at        timestamptz,
  error               text,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),
  metadata            jsonb DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.sync_logs IS 'Log of data synchronization runs between the platform and connected apps.';

CREATE INDEX idx_sync_logs_org_id ON public.sync_logs(org_id);
CREATE INDEX idx_sync_logs_app_id ON public.sync_logs(app_id);
CREATE INDEX idx_sync_logs_status ON public.sync_logs(status);
CREATE INDEX idx_sync_logs_direction ON public.sync_logs(direction);

CREATE TRIGGER trg_sync_logs_updated_at BEFORE UPDATE ON public.sync_logs
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- RLS
-- -----------------------------------------------------------------------------

-- connected_apps
ALTER TABLE public.connected_apps ENABLE ROW LEVEL SECURITY;

CREATE POLICY "connected_apps_select" ON public.connected_apps
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "connected_apps_insert" ON public.connected_apps
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "connected_apps_update" ON public.connected_apps
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "connected_apps_delete" ON public.connected_apps
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- oauth_tokens
ALTER TABLE public.oauth_tokens ENABLE ROW LEVEL SECURITY;

CREATE POLICY "oauth_tokens_select" ON public.oauth_tokens
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "oauth_tokens_insert" ON public.oauth_tokens
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "oauth_tokens_update" ON public.oauth_tokens
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "oauth_tokens_delete" ON public.oauth_tokens
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- webhooks
ALTER TABLE public.webhooks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "webhooks_select" ON public.webhooks
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "webhooks_insert" ON public.webhooks
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "webhooks_update" ON public.webhooks
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "webhooks_delete" ON public.webhooks
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- webhook_events
ALTER TABLE public.webhook_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "webhook_events_select" ON public.webhook_events
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "webhook_events_insert" ON public.webhook_events
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "webhook_events_update" ON public.webhook_events
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "webhook_events_delete" ON public.webhook_events
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- sync_logs
ALTER TABLE public.sync_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "sync_logs_select" ON public.sync_logs
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "sync_logs_insert" ON public.sync_logs
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "sync_logs_update" ON public.sync_logs
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "sync_logs_delete" ON public.sync_logs
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());
