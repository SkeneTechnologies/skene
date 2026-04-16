-- knowledge skill: articles, categories, and category links
-- Depends on content.

-- =============================================================================
-- 1. Enums
-- =============================================================================

CREATE TYPE public.article_status AS ENUM ('draft', 'published', 'archived');

-- =============================================================================
-- 2. Tables
-- =============================================================================

CREATE TABLE public.articles (
  id               uuid              PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid              NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  author_id        uuid              REFERENCES public.users (id) ON DELETE SET NULL,
  title            text              NOT NULL,
  slug             text              NOT NULL,
  body             text,
  excerpt          text,
  status           public.article_status NOT NULL DEFAULT 'draft',
  is_featured      boolean           NOT NULL DEFAULT false,
  view_count       integer           NOT NULL DEFAULT 0,
  published_at     timestamptz,
  created_at       timestamptz       NOT NULL DEFAULT now(),
  updated_at       timestamptz       NOT NULL DEFAULT now(),
  metadata         jsonb             DEFAULT '{}'::jsonb,
  UNIQUE (org_id, slug)
);

CREATE TABLE public.article_categories (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid        NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  name             text        NOT NULL,
  slug             text        NOT NULL,
  description      text,
  parent_id        uuid        REFERENCES public.article_categories (id) ON DELETE CASCADE,
  position         integer     NOT NULL DEFAULT 0,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  metadata         jsonb       DEFAULT '{}'::jsonb,
  UNIQUE (org_id, slug)
);

CREATE TABLE public.article_category_links (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid        NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  article_id       uuid        NOT NULL REFERENCES public.articles (id) ON DELETE CASCADE,
  category_id      uuid        NOT NULL REFERENCES public.article_categories (id) ON DELETE CASCADE,
  position         integer     NOT NULL DEFAULT 0,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  metadata         jsonb       DEFAULT '{}'::jsonb,
  UNIQUE (article_id, category_id)
);

-- =============================================================================
-- 3. Indexes
-- =============================================================================

CREATE INDEX idx_articles_org_id        ON public.articles (org_id);
CREATE INDEX idx_articles_author_id     ON public.articles (author_id);
CREATE INDEX idx_articles_status        ON public.articles (status);
CREATE INDEX idx_articles_is_featured   ON public.articles (is_featured) WHERE is_featured = true;
CREATE INDEX idx_articles_published_at  ON public.articles (published_at);

CREATE INDEX idx_article_categories_org_id    ON public.article_categories (org_id);
CREATE INDEX idx_article_categories_parent_id ON public.article_categories (parent_id);

CREATE INDEX idx_article_category_links_org_id      ON public.article_category_links (org_id);
CREATE INDEX idx_article_category_links_article_id   ON public.article_category_links (article_id);
CREATE INDEX idx_article_category_links_category_id  ON public.article_category_links (category_id);

-- =============================================================================
-- 4. Triggers
-- =============================================================================

CREATE TRIGGER trg_articles_updated_at BEFORE UPDATE ON public.articles
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_article_categories_updated_at BEFORE UPDATE ON public.article_categories
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_article_category_links_updated_at BEFORE UPDATE ON public.article_category_links
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- =============================================================================
-- 5. Comments
-- =============================================================================

COMMENT ON TABLE public.articles IS 'Knowledge base articles with slug-based URLs, view tracking, and featured flags.';
COMMENT ON COLUMN public.articles.slug IS 'URL-friendly identifier, unique per org.';
COMMENT ON COLUMN public.articles.excerpt IS 'Short summary for listings and search results.';
COMMENT ON COLUMN public.articles.is_featured IS 'Pinned articles shown prominently in the knowledge base.';
COMMENT ON COLUMN public.articles.view_count IS 'Read counter, incremented by the application layer.';

COMMENT ON TABLE public.article_categories IS 'Hierarchical categories for organizing articles. parent_id is NULL for top-level categories.';
COMMENT ON COLUMN public.article_categories.parent_id IS 'NULL for top-level categories, cascades on delete.';
COMMENT ON COLUMN public.article_categories.position IS 'Sort order within the same parent.';

COMMENT ON TABLE public.article_category_links IS 'Many-to-many link between articles and categories.';

-- =============================================================================
-- 6. Row-Level Security
-- =============================================================================

ALTER TABLE public.articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.article_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.article_category_links ENABLE ROW LEVEL SECURITY;

-- articles --------------------------------------------------------------------

CREATE POLICY articles_select ON public.articles
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY articles_insert ON public.articles
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY articles_update ON public.articles
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY articles_delete ON public.articles
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- article_categories ----------------------------------------------------------

CREATE POLICY article_categories_select ON public.article_categories
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY article_categories_insert ON public.article_categories
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY article_categories_update ON public.article_categories
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY article_categories_delete ON public.article_categories
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- article_category_links ------------------------------------------------------

CREATE POLICY article_category_links_select ON public.article_category_links
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY article_category_links_insert ON public.article_category_links
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY article_category_links_update ON public.article_category_links
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY article_category_links_delete ON public.article_category_links
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());
