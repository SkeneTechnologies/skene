-- =============================================================================
-- Skill: analytics
-- Depends on: identity
-- Description: Tags, custom fields, and activity log. Cross-cutting data layer.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Enums
-- -----------------------------------------------------------------------------
CREATE TYPE public.field_type AS ENUM ('text', 'number', 'boolean', 'date', 'select', 'multi_select', 'url', 'email');
CREATE TYPE public.activity_action AS ENUM (
  'created', 'updated', 'deleted', 'status_changed', 'assigned',
  'commented', 'viewed', 'email_sent', 'email_received', 'note_added',
  'call_logged', 'stage_changed', 'deal_won', 'deal_lost',
  'task_completed', 'payment_received'
);

-- -----------------------------------------------------------------------------
-- Table: tags
-- Org-scoped labels for any entity type.
-- -----------------------------------------------------------------------------
CREATE TABLE public.tags (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  name            text NOT NULL,
  color           text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb,
  UNIQUE(org_id, name)
);

COMMENT ON TABLE public.tags IS 'Org-scoped labels that can be applied to any entity.';

CREATE INDEX idx_tags_org_id ON public.tags(org_id);

CREATE TRIGGER trg_tags_updated_at BEFORE UPDATE ON public.tags
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: taggings
-- Polymorphic join between tags and entities.
-- -----------------------------------------------------------------------------
CREATE TABLE public.taggings (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  tag_id          uuid NOT NULL REFERENCES public.tags(id) ON DELETE CASCADE,
  entity_type     text NOT NULL,
  entity_id       uuid NOT NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb,
  UNIQUE(tag_id, entity_type, entity_id),
  CHECK (entity_type IN ('contact', 'company', 'deal', 'task', 'ticket', 'document', 'project', 'event'))
);

COMMENT ON TABLE public.taggings IS 'Polymorphic join between tags and any entity.';

CREATE INDEX idx_taggings_org_id ON public.taggings(org_id);
CREATE INDEX idx_taggings_tag_id ON public.taggings(tag_id);
CREATE INDEX idx_taggings_entity ON public.taggings(entity_type, entity_id);

CREATE TRIGGER trg_taggings_updated_at BEFORE UPDATE ON public.taggings
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: custom_field_definitions
-- Schema for user-defined fields per entity type.
-- -----------------------------------------------------------------------------
CREATE TABLE public.custom_field_definitions (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  entity_type     text NOT NULL,
  name            text NOT NULL,
  field_type      public.field_type NOT NULL DEFAULT 'text',
  description     text,
  is_required     boolean NOT NULL DEFAULT false,
  options         jsonb,
  position        integer NOT NULL DEFAULT 0,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb,
  UNIQUE(org_id, entity_type, name),
  CHECK (entity_type IN ('contact', 'company', 'deal', 'task', 'ticket', 'document', 'project'))
);

COMMENT ON COLUMN public.custom_field_definitions.options IS 'JSON array of allowed values for select/multi_select fields.';

CREATE INDEX idx_custom_field_definitions_org_id ON public.custom_field_definitions(org_id);
CREATE INDEX idx_custom_field_definitions_entity_type ON public.custom_field_definitions(entity_type);

CREATE TRIGGER trg_custom_field_definitions_updated_at BEFORE UPDATE ON public.custom_field_definitions
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: custom_field_values
-- Stores one typed column per data type to preserve type safety.
-- -----------------------------------------------------------------------------
CREATE TABLE public.custom_field_values (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  field_id        uuid NOT NULL REFERENCES public.custom_field_definitions(id) ON DELETE CASCADE,
  entity_type     text NOT NULL,
  entity_id       uuid NOT NULL,
  value_text      text,
  value_number    numeric,
  value_boolean   boolean,
  value_date      date,
  value_json      jsonb,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb,
  UNIQUE(field_id, entity_type, entity_id),
  CHECK (entity_type IN ('contact', 'company', 'deal', 'task', 'ticket', 'document', 'project'))
);

COMMENT ON TABLE public.custom_field_values IS 'One typed column per data type to preserve type safety.';

CREATE INDEX idx_custom_field_values_org_id ON public.custom_field_values(org_id);
CREATE INDEX idx_custom_field_values_field_id ON public.custom_field_values(field_id);
CREATE INDEX idx_custom_field_values_entity ON public.custom_field_values(entity_type, entity_id);

CREATE TRIGGER trg_custom_field_values_updated_at BEFORE UPDATE ON public.custom_field_values
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: activities
-- Append-only audit log for all entity changes.
-- -----------------------------------------------------------------------------
CREATE TABLE public.activities (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  actor_id        uuid REFERENCES public.users(id) ON DELETE SET NULL,
  entity_type     text NOT NULL,
  entity_id       uuid NOT NULL,
  action          public.activity_action NOT NULL,
  description     text,
  changes         jsonb,
  occurred_at     timestamptz NOT NULL DEFAULT now(),
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb,
  CHECK (entity_type IN ('contact', 'company', 'deal', 'task', 'ticket', 'document', 'project', 'subscription', 'invoice', 'event'))
);

COMMENT ON TABLE public.activities IS 'Append-only audit log for entity changes.';
COMMENT ON COLUMN public.activities.actor_id IS 'NULL for system-generated activities.';
COMMENT ON COLUMN public.activities.changes IS 'JSON diff, e.g. {"status": {"from": "open", "to": "closed"}}.';
COMMENT ON COLUMN public.activities.occurred_at IS 'Can differ from created_at for imported data.';

CREATE INDEX idx_activities_org_id ON public.activities(org_id);
CREATE INDEX idx_activities_entity ON public.activities(entity_type, entity_id);
CREATE INDEX idx_activities_actor_id ON public.activities(actor_id);
CREATE INDEX idx_activities_action ON public.activities(action);
CREATE INDEX idx_activities_occurred_at ON public.activities(occurred_at);

CREATE TRIGGER trg_activities_updated_at BEFORE UPDATE ON public.activities
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- RLS
-- -----------------------------------------------------------------------------

-- tags
ALTER TABLE public.tags ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tags_select" ON public.tags
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "tags_insert" ON public.tags
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "tags_update" ON public.tags
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "tags_delete" ON public.tags
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- taggings
ALTER TABLE public.taggings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "taggings_select" ON public.taggings
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "taggings_insert" ON public.taggings
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "taggings_update" ON public.taggings
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "taggings_delete" ON public.taggings
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- custom_field_definitions
ALTER TABLE public.custom_field_definitions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "custom_field_definitions_select" ON public.custom_field_definitions
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "custom_field_definitions_insert" ON public.custom_field_definitions
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "custom_field_definitions_update" ON public.custom_field_definitions
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "custom_field_definitions_delete" ON public.custom_field_definitions
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- custom_field_values
ALTER TABLE public.custom_field_values ENABLE ROW LEVEL SECURITY;

CREATE POLICY "custom_field_values_select" ON public.custom_field_values
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "custom_field_values_insert" ON public.custom_field_values
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "custom_field_values_update" ON public.custom_field_values
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "custom_field_values_delete" ON public.custom_field_values
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- activities
ALTER TABLE public.activities ENABLE ROW LEVEL SECURITY;

CREATE POLICY "activities_select" ON public.activities
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "activities_insert" ON public.activities
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "activities_update" ON public.activities
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "activities_delete" ON public.activities
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());
