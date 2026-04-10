-- =============================================================================
-- Migration: 00011_flexible_data
-- Description: Tags, taggings, custom field definitions, and custom field values.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Enums
-- -----------------------------------------------------------------------------
CREATE TYPE public.field_type AS ENUM ('text', 'number', 'boolean', 'date', 'select', 'multi_select', 'url', 'email');

-- -----------------------------------------------------------------------------
-- Table: tags
-- Org-scoped labels that can be applied to any entity.
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

COMMENT ON TABLE public.tags IS 'Org-scoped labels. Applied to any entity via the taggings join table.';

CREATE INDEX idx_tags_org_id ON public.tags(org_id);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.tags
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: taggings
-- Polymorphic join: applies a tag to any entity.
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

COMMENT ON TABLE public.taggings IS 'Polymorphic join table. Links tags to any entity.';

CREATE INDEX idx_taggings_org_id ON public.taggings(org_id);
CREATE INDEX idx_taggings_tag_id ON public.taggings(tag_id);
CREATE INDEX idx_taggings_entity ON public.taggings(entity_type, entity_id);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.taggings
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: custom_field_definitions
-- Defines custom fields scoped to an entity type within an org.
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

COMMENT ON TABLE public.custom_field_definitions IS 'Defines org-scoped custom fields for any entity type.';
COMMENT ON COLUMN public.custom_field_definitions.options IS 'JSON array of allowed values for select/multi_select fields.';
COMMENT ON COLUMN public.custom_field_definitions.field_type IS 'Data type: text, number, boolean, date, select, multi_select, url, email.';

CREATE INDEX idx_custom_field_definitions_org_id ON public.custom_field_definitions(org_id);
CREATE INDEX idx_custom_field_definitions_entity_type ON public.custom_field_definitions(entity_type);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.custom_field_definitions
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: custom_field_values
-- Stores the actual value of a custom field for a specific entity instance.
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

COMMENT ON TABLE public.custom_field_values IS 'Stores custom field values for entity instances. One typed column per data type.';
COMMENT ON COLUMN public.custom_field_values.value_text IS 'Value for text, select, url, email field types.';
COMMENT ON COLUMN public.custom_field_values.value_number IS 'Value for number field type.';
COMMENT ON COLUMN public.custom_field_values.value_boolean IS 'Value for boolean field type.';
COMMENT ON COLUMN public.custom_field_values.value_date IS 'Value for date field type.';
COMMENT ON COLUMN public.custom_field_values.value_json IS 'Value for multi_select and complex field types.';

CREATE INDEX idx_custom_field_values_org_id ON public.custom_field_values(org_id);
CREATE INDEX idx_custom_field_values_field_id ON public.custom_field_values(field_id);
CREATE INDEX idx_custom_field_values_entity ON public.custom_field_values(entity_type, entity_id);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.custom_field_values
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
