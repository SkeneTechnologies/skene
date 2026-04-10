-- =============================================================================
-- Migration: 00007_content
-- Description: Folders, documents, and comments (polymorphic).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Enums
-- -----------------------------------------------------------------------------
CREATE TYPE public.document_status AS ENUM ('draft', 'published', 'archived');

-- -----------------------------------------------------------------------------
-- Table: folders
-- Hierarchical folder structure. Self-referencing parent_id.
-- -----------------------------------------------------------------------------
CREATE TABLE public.folders (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  parent_id       uuid REFERENCES public.folders(id) ON DELETE CASCADE,
  name            text NOT NULL,
  description     text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.folders IS 'Hierarchical folder structure. Deleting a parent cascades to children.';
COMMENT ON COLUMN public.folders.parent_id IS 'Parent folder. NULL means root-level folder.';

CREATE INDEX idx_folders_org_id ON public.folders(org_id);
CREATE INDEX idx_folders_parent_id ON public.folders(parent_id);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.folders
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: documents
-- Content items (wiki pages, notes, files) within folders.
-- -----------------------------------------------------------------------------
CREATE TABLE public.documents (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  folder_id       uuid REFERENCES public.folders(id) ON DELETE SET NULL,
  author_id       uuid REFERENCES public.users(id) ON DELETE SET NULL,
  title           text NOT NULL,
  body            text,
  status          public.document_status NOT NULL DEFAULT 'draft',
  published_at    timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.documents IS 'Content items: wiki pages, notes, file references. Optionally organized in folders.';

CREATE INDEX idx_documents_org_id ON public.documents(org_id);
CREATE INDEX idx_documents_folder_id ON public.documents(folder_id);
CREATE INDEX idx_documents_author_id ON public.documents(author_id);
CREATE INDEX idx_documents_status ON public.documents(status);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.documents
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: comments
-- Polymorphic comments on any entity (task, ticket, document, deal, etc).
-- -----------------------------------------------------------------------------
CREATE TABLE public.comments (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  author_id       uuid REFERENCES public.users(id) ON DELETE SET NULL,
  entity_type     text NOT NULL,
  entity_id       uuid NOT NULL,
  body            text NOT NULL,
  parent_id       uuid REFERENCES public.comments(id) ON DELETE CASCADE,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb,
  CHECK (entity_type IN ('task', 'ticket', 'document', 'deal', 'project', 'contact', 'company'))
);

COMMENT ON TABLE public.comments IS 'Polymorphic comments. Attaches to any entity. Supports threaded replies via parent_id.';

CREATE INDEX idx_comments_org_id ON public.comments(org_id);
CREATE INDEX idx_comments_entity ON public.comments(entity_type, entity_id);
CREATE INDEX idx_comments_author_id ON public.comments(author_id);
CREATE INDEX idx_comments_parent_id ON public.comments(parent_id);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.comments
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
