-- tasks skill: projects, tasks, task dependencies
-- Depends on identity.

-- =============================================================================
-- 1. Enums
-- =============================================================================

CREATE TYPE public.task_status AS ENUM ('todo', 'in_progress', 'in_review', 'done', 'cancelled');
CREATE TYPE public.task_priority AS ENUM ('low', 'medium', 'high', 'urgent');

-- =============================================================================
-- 2. Tables
-- =============================================================================

CREATE TABLE public.projects (
  id               uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid          NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  owner_id         uuid          REFERENCES public.users (id) ON DELETE SET NULL,
  name             text          NOT NULL,
  description      text,
  status           public.task_status   NOT NULL DEFAULT 'todo',
  priority         public.task_priority NOT NULL DEFAULT 'medium',
  starts_at        date,
  due_at           date,
  completed_at     timestamptz,
  created_at       timestamptz   NOT NULL DEFAULT now(),
  updated_at       timestamptz   NOT NULL DEFAULT now(),
  metadata         jsonb         DEFAULT '{}'::jsonb
);

CREATE TABLE public.tasks (
  id               uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid          NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  project_id       uuid          REFERENCES public.projects (id) ON DELETE CASCADE,
  assignee_id      uuid          REFERENCES public.users (id) ON DELETE SET NULL,
  creator_id       uuid          REFERENCES public.users (id) ON DELETE SET NULL,
  title            text          NOT NULL,
  description      text,
  status           public.task_status   NOT NULL DEFAULT 'todo',
  priority         public.task_priority NOT NULL DEFAULT 'medium',
  due_at           date,
  completed_at     timestamptz,
  position         integer       NOT NULL DEFAULT 0,
  created_at       timestamptz   NOT NULL DEFAULT now(),
  updated_at       timestamptz   NOT NULL DEFAULT now(),
  metadata         jsonb         DEFAULT '{}'::jsonb
);

CREATE TABLE public.task_dependencies (
  id               uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid          NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  task_id          uuid          NOT NULL REFERENCES public.tasks (id) ON DELETE CASCADE,
  depends_on_id    uuid          NOT NULL REFERENCES public.tasks (id) ON DELETE CASCADE,
  created_at       timestamptz   NOT NULL DEFAULT now(),
  updated_at       timestamptz   NOT NULL DEFAULT now(),
  metadata         jsonb         DEFAULT '{}'::jsonb,
  UNIQUE (task_id, depends_on_id),
  CHECK (task_id != depends_on_id)
);

-- =============================================================================
-- 3. Indexes
-- =============================================================================

CREATE INDEX idx_projects_org_id    ON public.projects (org_id);
CREATE INDEX idx_projects_owner_id  ON public.projects (owner_id);
CREATE INDEX idx_projects_status    ON public.projects (status);

CREATE INDEX idx_tasks_org_id       ON public.tasks (org_id);
CREATE INDEX idx_tasks_project_id   ON public.tasks (project_id);
CREATE INDEX idx_tasks_assignee_id  ON public.tasks (assignee_id);
CREATE INDEX idx_tasks_status       ON public.tasks (status);
CREATE INDEX idx_tasks_priority     ON public.tasks (priority);
CREATE INDEX idx_tasks_due_at       ON public.tasks (due_at);

CREATE INDEX idx_task_dependencies_org_id        ON public.task_dependencies (org_id);
CREATE INDEX idx_task_dependencies_task_id        ON public.task_dependencies (task_id);
CREATE INDEX idx_task_dependencies_depends_on_id  ON public.task_dependencies (depends_on_id);

-- =============================================================================
-- 4. Triggers
-- =============================================================================

CREATE TRIGGER trg_projects_updated_at BEFORE UPDATE ON public.projects
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_tasks_updated_at BEFORE UPDATE ON public.tasks
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_task_dependencies_updated_at BEFORE UPDATE ON public.task_dependencies
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- =============================================================================
-- 5. Comments
-- =============================================================================

COMMENT ON TABLE public.projects IS 'Container for related tasks.';
COMMENT ON TABLE public.tasks IS 'Individual work items, optionally grouped under a project.';
COMMENT ON TABLE public.task_dependencies IS 'Blocking relationships between tasks.';

COMMENT ON COLUMN public.tasks.position IS 'Sort order within project.';

-- =============================================================================
-- 6. Row-Level Security
-- =============================================================================

ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.task_dependencies ENABLE ROW LEVEL SECURITY;

-- projects --------------------------------------------------------------------

CREATE POLICY projects_select ON public.projects
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY projects_insert ON public.projects
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY projects_update ON public.projects
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY projects_delete ON public.projects
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- tasks -----------------------------------------------------------------------

CREATE POLICY tasks_select ON public.tasks
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY tasks_insert ON public.tasks
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY tasks_update ON public.tasks
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY tasks_delete ON public.tasks
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- task_dependencies -----------------------------------------------------------

CREATE POLICY task_dependencies_select ON public.task_dependencies
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY task_dependencies_insert ON public.task_dependencies
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY task_dependencies_update ON public.task_dependencies
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY task_dependencies_delete ON public.task_dependencies
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());
