-- content skill: folders, documents, comments
-- Depends on identity.

-- =============================================================================
-- 1. Enums
-- =============================================================================

CREATE TYPE public.document_status AS ENUM ('draft', 'published', 'archived');

-- =============================================================================
-- 2. Tables
-- =============================================================================

CREATE TABLE public.folders (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid        NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  parent_id        uuid        REFERENCES public.folders (id) ON DELETE CASCADE,
  name             text        NOT NULL,
  description      text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  metadata         jsonb       DEFAULT '{}'::jsonb
);

CREATE TABLE public.documents (
  id               uuid                  PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid                  NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  folder_id        uuid                  REFERENCES public.folders (id) ON DELETE SET NULL,
  author_id        uuid                  REFERENCES public.users (id) ON DELETE SET NULL,
  title            text                  NOT NULL,
  body             text,
  status           public.document_status NOT NULL DEFAULT 'draft',
  published_at     timestamptz,
  created_at       timestamptz           NOT NULL DEFAULT now(),
  updated_at       timestamptz           NOT NULL DEFAULT now(),
  metadata         jsonb                 DEFAULT '{}'::jsonb
);

CREATE TABLE public.comments (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid        NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  author_id        uuid        REFERENCES public.users (id) ON DELETE SET NULL,
  entity_type      text        NOT NULL,
  entity_id        uuid        NOT NULL,
  body             text        NOT NULL,
  parent_id        uuid        REFERENCES public.comments (id) ON DELETE CASCADE,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  metadata         jsonb       DEFAULT '{}'::jsonb,
  CHECK (entity_type IN ('task', 'ticket', 'document', 'deal', 'project', 'contact', 'company'))
);

-- =============================================================================
-- 3. Indexes
-- =============================================================================

CREATE INDEX idx_folders_org_id      ON public.folders (org_id);
CREATE INDEX idx_folders_parent_id   ON public.folders (parent_id);

CREATE INDEX idx_documents_org_id    ON public.documents (org_id);
CREATE INDEX idx_documents_folder_id ON public.documents (folder_id);
CREATE INDEX idx_documents_author_id ON public.documents (author_id);
CREATE INDEX idx_documents_status    ON public.documents (status);

CREATE INDEX idx_comments_org_id     ON public.comments (org_id);
CREATE INDEX idx_comments_entity     ON public.comments (entity_type, entity_id);
CREATE INDEX idx_comments_author_id  ON public.comments (author_id);
CREATE INDEX idx_comments_parent_id  ON public.comments (parent_id);

-- =============================================================================
-- 4. Triggers
-- =============================================================================

CREATE TRIGGER trg_folders_updated_at BEFORE UPDATE ON public.folders
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_documents_updated_at BEFORE UPDATE ON public.documents
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_comments_updated_at BEFORE UPDATE ON public.comments
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- =============================================================================
-- 5. Comments
-- =============================================================================

COMMENT ON TABLE public.folders IS 'Hierarchical folder tree. parent_id is NULL for root folders.';
COMMENT ON COLUMN public.folders.parent_id IS 'NULL for root folders, cascades on delete.';

COMMENT ON TABLE public.documents IS 'Wiki pages, notes, and file references.';

COMMENT ON TABLE public.comments IS 'Polymorphic comments with threaded replies via parent_id.';
COMMENT ON COLUMN public.comments.entity_type IS 'The type of record this comment belongs to.';
COMMENT ON COLUMN public.comments.entity_id IS 'The ID of the record this comment belongs to.';

-- =============================================================================
-- 6. Row-Level Security
-- =============================================================================

ALTER TABLE public.folders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.comments ENABLE ROW LEVEL SECURITY;

-- folders ---------------------------------------------------------------------

CREATE POLICY folders_select ON public.folders
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY folders_insert ON public.folders
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY folders_update ON public.folders
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY folders_delete ON public.folders
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- documents -------------------------------------------------------------------

CREATE POLICY documents_select ON public.documents
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY documents_insert ON public.documents
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY documents_update ON public.documents
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY documents_delete ON public.documents
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- comments --------------------------------------------------------------------

CREATE POLICY comments_select ON public.comments
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY comments_insert ON public.comments
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY comments_update ON public.comments
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY comments_delete ON public.comments
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());
