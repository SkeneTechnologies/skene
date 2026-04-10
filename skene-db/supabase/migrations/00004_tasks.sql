-- =============================================================================
-- Migration: 00004_tasks
-- Description: Projects, tasks, and task dependencies.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Enums
-- -----------------------------------------------------------------------------
CREATE TYPE public.task_status AS ENUM ('todo', 'in_progress', 'in_review', 'done', 'cancelled');
CREATE TYPE public.task_priority AS ENUM ('low', 'medium', 'high', 'urgent');

-- -----------------------------------------------------------------------------
-- Table: projects
-- A container for related tasks.
-- -----------------------------------------------------------------------------
CREATE TABLE public.projects (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  owner_id        uuid REFERENCES public.users(id) ON DELETE SET NULL,
  name            text NOT NULL,
  description     text,
  status          public.task_status NOT NULL DEFAULT 'todo',
  priority        public.task_priority NOT NULL DEFAULT 'medium',
  starts_at       date,
  due_at          date,
  completed_at    timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.projects IS 'A container for related tasks. Has its own status and timeline.';

CREATE INDEX idx_projects_org_id ON public.projects(org_id);
CREATE INDEX idx_projects_owner_id ON public.projects(owner_id);
CREATE INDEX idx_projects_status ON public.projects(status);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.projects
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: tasks
-- Individual work items within a project.
-- -----------------------------------------------------------------------------
CREATE TABLE public.tasks (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  project_id      uuid REFERENCES public.projects(id) ON DELETE CASCADE,
  assignee_id     uuid REFERENCES public.users(id) ON DELETE SET NULL,
  creator_id      uuid REFERENCES public.users(id) ON DELETE SET NULL,
  title           text NOT NULL,
  description     text,
  status          public.task_status NOT NULL DEFAULT 'todo',
  priority        public.task_priority NOT NULL DEFAULT 'medium',
  due_at          date,
  completed_at    timestamptz,
  position        integer NOT NULL DEFAULT 0,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.tasks IS 'Individual work items. Can belong to a project or stand alone.';
COMMENT ON COLUMN public.tasks.position IS 'Sort order within a project.';

CREATE INDEX idx_tasks_org_id ON public.tasks(org_id);
CREATE INDEX idx_tasks_project_id ON public.tasks(project_id);
CREATE INDEX idx_tasks_assignee_id ON public.tasks(assignee_id);
CREATE INDEX idx_tasks_status ON public.tasks(status);
CREATE INDEX idx_tasks_priority ON public.tasks(priority);
CREATE INDEX idx_tasks_due_at ON public.tasks(due_at);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.tasks
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: task_dependencies
-- Defines blocking relationships between tasks.
-- -----------------------------------------------------------------------------
CREATE TABLE public.task_dependencies (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  task_id         uuid NOT NULL REFERENCES public.tasks(id) ON DELETE CASCADE,
  depends_on_id   uuid NOT NULL REFERENCES public.tasks(id) ON DELETE CASCADE,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb,
  UNIQUE(task_id, depends_on_id),
  CHECK (task_id != depends_on_id)
);

COMMENT ON TABLE public.task_dependencies IS 'Defines which tasks block other tasks. task_id depends on depends_on_id.';

CREATE INDEX idx_task_dependencies_org_id ON public.task_dependencies(org_id);
CREATE INDEX idx_task_dependencies_task_id ON public.task_dependencies(task_id);
CREATE INDEX idx_task_dependencies_depends_on_id ON public.task_dependencies(depends_on_id);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.task_dependencies
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
