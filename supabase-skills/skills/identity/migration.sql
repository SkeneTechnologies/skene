-- identity skill: organizations, users, teams, memberships, roles, permissions
-- Foundation schema for multi-tenant Supabase apps with RLS.

-- =============================================================================
-- 1. Trigger function
-- =============================================================================

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- 2. RLS helper functions
-- =============================================================================

CREATE OR REPLACE FUNCTION public.get_user_org_id()
RETURNS uuid AS $$
  SELECT org_id FROM public.users WHERE auth_id = auth.uid() LIMIT 1;
$$ LANGUAGE sql SECURITY DEFINER STABLE;

CREATE OR REPLACE FUNCTION public.get_user_role()
RETURNS public.membership_role AS $$
  SELECT m.role FROM public.memberships m
  JOIN public.users u ON u.id = m.user_id
  WHERE u.auth_id = auth.uid()
    AND m.org_id = u.org_id
    AND m.status = 'active'
  LIMIT 1;
$$ LANGUAGE sql SECURITY DEFINER STABLE;

CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS boolean AS $$
  SELECT public.get_user_role() IN ('admin', 'owner');
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- =============================================================================
-- 3. Enums
-- =============================================================================

CREATE TYPE public.membership_role AS ENUM ('owner', 'admin', 'member', 'guest');
CREATE TYPE public.membership_status AS ENUM ('active', 'invited', 'suspended');

-- =============================================================================
-- 4. Tables
-- =============================================================================

CREATE TABLE public.organizations (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  name             text        NOT NULL,
  slug             text        NOT NULL UNIQUE,
  logo_url         text,
  domain           text,
  stripe_customer_id text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  metadata         jsonb       DEFAULT '{}'::jsonb
);

CREATE TABLE public.users (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid        NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  auth_id          uuid        UNIQUE,
  email            text        NOT NULL,
  full_name        text,
  avatar_url       text,
  phone            text,
  timezone         text        DEFAULT 'UTC',
  is_active        boolean     NOT NULL DEFAULT true,
  last_sign_in_at  timestamptz,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  metadata         jsonb       DEFAULT '{}'::jsonb
);

CREATE TABLE public.teams (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid        NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  name             text        NOT NULL,
  description      text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  metadata         jsonb       DEFAULT '{}'::jsonb
);

CREATE TABLE public.memberships (
  id               uuid                   PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid                   NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  user_id          uuid                   NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  team_id          uuid                   REFERENCES public.teams (id) ON DELETE SET NULL,
  role             public.membership_role  NOT NULL DEFAULT 'member',
  status           public.membership_status NOT NULL DEFAULT 'active',
  created_at       timestamptz            NOT NULL DEFAULT now(),
  updated_at       timestamptz            NOT NULL DEFAULT now(),
  metadata         jsonb                  DEFAULT '{}'::jsonb,
  UNIQUE (org_id, user_id)
);

CREATE TABLE public.roles (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid        NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  name             text        NOT NULL,
  description      text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  metadata         jsonb       DEFAULT '{}'::jsonb,
  UNIQUE (org_id, name)
);

CREATE TABLE public.permissions (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid        NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  role_id          uuid        NOT NULL REFERENCES public.roles (id) ON DELETE CASCADE,
  resource         text        NOT NULL,
  action           text        NOT NULL,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  metadata         jsonb       DEFAULT '{}'::jsonb,
  UNIQUE (role_id, resource, action)
);

-- =============================================================================
-- 5. Indexes
-- =============================================================================

CREATE INDEX idx_organizations_slug   ON public.organizations (slug);
CREATE INDEX idx_users_org_id         ON public.users (org_id);
CREATE INDEX idx_users_email          ON public.users (email);
CREATE UNIQUE INDEX idx_users_auth_id ON public.users (auth_id) WHERE auth_id IS NOT NULL;
CREATE INDEX idx_teams_org_id         ON public.teams (org_id);
CREATE INDEX idx_memberships_org_id   ON public.memberships (org_id);
CREATE INDEX idx_memberships_user_id  ON public.memberships (user_id);
CREATE INDEX idx_memberships_team_id  ON public.memberships (team_id);
CREATE INDEX idx_roles_org_id         ON public.roles (org_id);
CREATE INDEX idx_permissions_org_id   ON public.permissions (org_id);
CREATE INDEX idx_permissions_role_id  ON public.permissions (role_id);

-- =============================================================================
-- 6. Triggers
-- =============================================================================

CREATE TRIGGER trg_organizations_updated_at BEFORE UPDATE ON public.organizations
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON public.users
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_teams_updated_at BEFORE UPDATE ON public.teams
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_memberships_updated_at BEFORE UPDATE ON public.memberships
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_roles_updated_at BEFORE UPDATE ON public.roles
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_permissions_updated_at BEFORE UPDATE ON public.permissions
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- =============================================================================
-- 7. Comments
-- =============================================================================

COMMENT ON TABLE public.organizations IS 'Top-level tenant. All data is scoped to an organization.';
COMMENT ON TABLE public.users IS 'Application user linked to a Supabase Auth identity and scoped to one org.';
COMMENT ON TABLE public.teams IS 'Grouping of users within an organization for team-based access.';
COMMENT ON TABLE public.memberships IS 'Junction between users, orgs, and optionally teams. Carries role and status.';
COMMENT ON TABLE public.roles IS 'Named role within an org, used to group permissions.';
COMMENT ON TABLE public.permissions IS 'Fine-grained permission grant: a role can perform an action on a resource.';

COMMENT ON COLUMN public.organizations.slug IS 'URL-safe unique identifier used in routes and subdomains.';
COMMENT ON COLUMN public.organizations.stripe_customer_id IS 'Stripe customer ID for billing integration. NULL if billing not configured.';
COMMENT ON COLUMN public.organizations.metadata IS 'Arbitrary JSON for org-level settings or feature flags.';
COMMENT ON COLUMN public.users.auth_id IS 'FK to auth.users(id). NULL for users invited but not yet signed up.';
COMMENT ON COLUMN public.users.is_active IS 'Soft-delete flag. Inactive users cannot sign in but their data is preserved.';
COMMENT ON COLUMN public.memberships.team_id IS 'Optional team assignment. NULL means the user belongs to the org but no specific team.';
COMMENT ON COLUMN public.permissions.resource IS 'Dot-notated resource identifier, e.g. "projects", "billing.invoices".';
COMMENT ON COLUMN public.permissions.action IS 'Operation allowed on the resource, e.g. "read", "write", "delete", "admin".';

-- =============================================================================
-- 8. Row-Level Security
-- =============================================================================

ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.permissions ENABLE ROW LEVEL SECURITY;

-- organizations ---------------------------------------------------------------

CREATE POLICY organizations_select ON public.organizations
  FOR SELECT USING (id = public.get_user_org_id());

CREATE POLICY organizations_insert ON public.organizations
  FOR INSERT WITH CHECK (true);

CREATE POLICY organizations_update ON public.organizations
  FOR UPDATE USING (id = public.get_user_org_id() AND public.is_admin());

CREATE POLICY organizations_delete ON public.organizations
  FOR DELETE USING (id = public.get_user_org_id() AND public.get_user_role() = 'owner');

-- users -----------------------------------------------------------------------

CREATE POLICY users_select ON public.users
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY users_insert ON public.users
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY users_update ON public.users
  FOR UPDATE USING (
    org_id = public.get_user_org_id()
    AND (auth_id = auth.uid() OR public.is_admin())
  );

CREATE POLICY users_delete ON public.users
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- teams -----------------------------------------------------------------------

CREATE POLICY teams_select ON public.teams
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY teams_insert ON public.teams
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY teams_update ON public.teams
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY teams_delete ON public.teams
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- memberships -----------------------------------------------------------------

CREATE POLICY memberships_select ON public.memberships
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY memberships_insert ON public.memberships
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id() AND public.is_admin());

CREATE POLICY memberships_update ON public.memberships
  FOR UPDATE USING (
    org_id = public.get_user_org_id()
    AND (
      user_id = (SELECT id FROM public.users WHERE auth_id = auth.uid() LIMIT 1)
      OR public.is_admin()
    )
  );

CREATE POLICY memberships_delete ON public.memberships
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- roles -----------------------------------------------------------------------

CREATE POLICY roles_select ON public.roles
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY roles_insert ON public.roles
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id() AND public.is_admin());

CREATE POLICY roles_update ON public.roles
  FOR UPDATE USING (org_id = public.get_user_org_id() AND public.is_admin());

CREATE POLICY roles_delete ON public.roles
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- permissions -----------------------------------------------------------------

CREATE POLICY permissions_select ON public.permissions
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY permissions_insert ON public.permissions
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id() AND public.is_admin());

CREATE POLICY permissions_update ON public.permissions
  FOR UPDATE USING (org_id = public.get_user_org_id() AND public.is_admin());

CREATE POLICY permissions_delete ON public.permissions
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());
