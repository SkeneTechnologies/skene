-- forms skill: form definitions, fields, submissions, and file uploads
-- Depends on identity for organizations and users.

-- =============================================================================
-- 1. Enums
-- =============================================================================

CREATE TYPE public.form_status AS ENUM ('draft', 'active', 'archived');
CREATE TYPE public.form_field_type AS ENUM ('text', 'email', 'number', 'select', 'multiselect', 'checkbox', 'textarea', 'date', 'file');

-- =============================================================================
-- 2. Tables
-- =============================================================================

CREATE TABLE public.form_definitions (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid        NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  creator_id       uuid        REFERENCES public.users (id) ON DELETE SET NULL,
  name             text        NOT NULL,
  slug             text        NOT NULL,
  description      text,
  status           public.form_status NOT NULL DEFAULT 'draft',
  submit_message   text,
  redirect_url     text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  metadata         jsonb       DEFAULT '{}'::jsonb,
  UNIQUE (org_id, slug)
);

CREATE TABLE public.form_fields (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid        NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  form_id          uuid        NOT NULL REFERENCES public.form_definitions (id) ON DELETE CASCADE,
  label            text        NOT NULL,
  field_key        text        NOT NULL,
  field_type       public.form_field_type NOT NULL DEFAULT 'text',
  position         integer     NOT NULL DEFAULT 0,
  is_required      boolean     NOT NULL DEFAULT false,
  options          jsonb,
  validation       jsonb,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  metadata         jsonb       DEFAULT '{}'::jsonb,
  UNIQUE (form_id, field_key)
);

CREATE TABLE public.form_submissions (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid        NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  form_id          uuid        NOT NULL REFERENCES public.form_definitions (id) ON DELETE CASCADE,
  contact_id       uuid,
  data             jsonb       NOT NULL DEFAULT '{}'::jsonb,
  submitted_at     timestamptz NOT NULL DEFAULT now(),
  ip_address       inet,
  user_agent       text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  metadata         jsonb       DEFAULT '{}'::jsonb
);

CREATE TABLE public.form_uploads (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid        NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  submission_id    uuid        NOT NULL REFERENCES public.form_submissions (id) ON DELETE CASCADE,
  field_id         uuid        REFERENCES public.form_fields (id) ON DELETE SET NULL,
  file_name        text        NOT NULL,
  file_size        bigint,
  mime_type        text,
  storage_path     text        NOT NULL,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  metadata         jsonb       DEFAULT '{}'::jsonb
);

-- =============================================================================
-- 3. Indexes
-- =============================================================================

CREATE INDEX idx_form_definitions_org_id    ON public.form_definitions (org_id);
CREATE INDEX idx_form_definitions_status    ON public.form_definitions (status);
CREATE INDEX idx_form_definitions_slug      ON public.form_definitions (slug);
CREATE INDEX idx_form_fields_org_id         ON public.form_fields (org_id);
CREATE INDEX idx_form_fields_form_id        ON public.form_fields (form_id);
CREATE INDEX idx_form_submissions_org_id    ON public.form_submissions (org_id);
CREATE INDEX idx_form_submissions_form_id   ON public.form_submissions (form_id);
CREATE INDEX idx_form_uploads_org_id        ON public.form_uploads (org_id);
CREATE INDEX idx_form_uploads_submission_id ON public.form_uploads (submission_id);

-- =============================================================================
-- 4. Triggers
-- =============================================================================

CREATE TRIGGER trg_form_definitions_updated_at BEFORE UPDATE ON public.form_definitions
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_form_fields_updated_at BEFORE UPDATE ON public.form_fields
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_form_submissions_updated_at BEFORE UPDATE ON public.form_submissions
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_form_uploads_updated_at BEFORE UPDATE ON public.form_uploads
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- =============================================================================
-- 5. Comments
-- =============================================================================

COMMENT ON TABLE public.form_definitions IS 'Configurable form with status lifecycle, scoped to an organization.';
COMMENT ON TABLE public.form_fields IS 'Ordered field within a form definition. Carries type, validation, and option config.';
COMMENT ON TABLE public.form_submissions IS 'Single submission of a form. Stores field values as JSON in the data column.';
COMMENT ON TABLE public.form_uploads IS 'File attached to a form submission, linked to the originating field.';

COMMENT ON COLUMN public.form_definitions.slug IS 'URL-safe identifier, unique per org. Used in public form URLs.';
COMMENT ON COLUMN public.form_definitions.status IS 'Lifecycle state: draft (not accepting submissions), active, or archived.';
COMMENT ON COLUMN public.form_definitions.submit_message IS 'Confirmation message shown after successful submission.';
COMMENT ON COLUMN public.form_fields.field_key IS 'Machine-readable key stored in submission data JSON. Unique per form.';
COMMENT ON COLUMN public.form_fields.position IS 'Display order within the form. Lower values appear first.';
COMMENT ON COLUMN public.form_fields.options IS 'JSON array of option objects for select/multiselect fields.';
COMMENT ON COLUMN public.form_fields.validation IS 'JSON object with validation rules, e.g. {"min_length": 3, "max_length": 500}.';
COMMENT ON COLUMN public.form_submissions.contact_id IS 'Optional reference to a CRM contact. Not enforced as FK to allow flexible linking.';
COMMENT ON COLUMN public.form_submissions.data IS 'JSON object mapping field_key to submitted value.';
COMMENT ON COLUMN public.form_uploads.storage_path IS 'Path within Supabase Storage where the uploaded file is stored.';

-- =============================================================================
-- 6. Row-Level Security
-- =============================================================================

ALTER TABLE public.form_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.form_fields ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.form_submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.form_uploads ENABLE ROW LEVEL SECURITY;

-- form_definitions ---------------------------------------------------------------

CREATE POLICY form_definitions_select ON public.form_definitions
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY form_definitions_insert ON public.form_definitions
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY form_definitions_update ON public.form_definitions
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY form_definitions_delete ON public.form_definitions
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- form_fields --------------------------------------------------------------------

CREATE POLICY form_fields_select ON public.form_fields
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY form_fields_insert ON public.form_fields
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY form_fields_update ON public.form_fields
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY form_fields_delete ON public.form_fields
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- form_submissions ---------------------------------------------------------------

CREATE POLICY form_submissions_select ON public.form_submissions
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY form_submissions_insert ON public.form_submissions
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY form_submissions_update ON public.form_submissions
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY form_submissions_delete ON public.form_submissions
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- form_uploads -------------------------------------------------------------------

CREATE POLICY form_uploads_select ON public.form_uploads
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY form_uploads_insert ON public.form_uploads
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY form_uploads_update ON public.form_uploads
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY form_uploads_delete ON public.form_uploads
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());
