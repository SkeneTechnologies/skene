-- =============================================================================
-- Migration: 00001_identity
-- Description: Foundation layer. Trigger function, RLS helpers, enums,
--              organizations, users, teams, memberships, roles, permissions.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Utility: updated_at trigger function
-- Applied to every table in the schema.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION public.set_updated_at()
  IS 'Sets updated_at to now() on every UPDATE. Attach as BEFORE UPDATE trigger.';

-- -----------------------------------------------------------------------------
-- RLS helper: get_user_org_id()
-- Returns the org_id for the currently authenticated user.
-- SECURITY DEFINER bypasses RLS on the users table to avoid circular deps.
-- STABLE tells the planner the result is constant within a statement.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.get_user_org_id()
RETURNS uuid AS $$
  SELECT org_id FROM public.users WHERE auth_id = auth.uid() LIMIT 1;
$$ LANGUAGE sql SECURITY DEFINER STABLE;

COMMENT ON FUNCTION public.get_user_org_id()
  IS 'Returns the org_id of the authenticated user. Used in every RLS policy.';

-- -----------------------------------------------------------------------------
-- RLS helper: get_user_role()
-- Returns the membership role for the authenticated user in their org.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.get_user_role()
RETURNS public.membership_role AS $$
  SELECT m.role FROM public.memberships m
  JOIN public.users u ON u.id = m.user_id
  WHERE u.auth_id = auth.uid()
    AND m.org_id = public.get_user_org_id()
  LIMIT 1;
$$ LANGUAGE sql SECURITY DEFINER STABLE;

COMMENT ON FUNCTION public.get_user_role()
  IS 'Returns the membership role (owner/admin/member/guest) of the authenticated user.';

-- -----------------------------------------------------------------------------
-- RLS helper: is_admin()
-- Returns true if the authenticated user has admin or owner role.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS boolean AS $$
  SELECT public.get_user_role() IN ('admin', 'owner');
$$ LANGUAGE sql SECURITY DEFINER STABLE;

COMMENT ON FUNCTION public.is_admin()
  IS 'Returns true if the authenticated user is an admin or owner.';

-- -----------------------------------------------------------------------------
-- Enums
-- -----------------------------------------------------------------------------
CREATE TYPE public.membership_role AS ENUM ('owner', 'admin', 'member', 'guest');
CREATE TYPE public.membership_status AS ENUM ('active', 'invited', 'suspended');

-- -----------------------------------------------------------------------------
-- Table: organizations
-- Root tenant table. Does not carry org_id because it IS the org.
-- -----------------------------------------------------------------------------
CREATE TABLE public.organizations (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name            text NOT NULL,
  slug            text NOT NULL UNIQUE,
  logo_url        text,
  domain          text,
  stripe_customer_id text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.organizations IS 'Root tenant table. Every other table references org_id back to this.';
COMMENT ON COLUMN public.organizations.slug IS 'URL-safe unique identifier for the organization.';
COMMENT ON COLUMN public.organizations.stripe_customer_id IS 'Optional Stripe customer ID for billing integration.';
COMMENT ON COLUMN public.organizations.metadata IS 'JSONB escape hatch for unstructured data.';

CREATE INDEX idx_organizations_slug ON public.organizations(slug);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.organizations
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: users
-- Maps to Supabase Auth via auth_id. One user belongs to one org (v1).
-- -----------------------------------------------------------------------------
CREATE TABLE public.users (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  auth_id         uuid UNIQUE,
  email           text NOT NULL,
  full_name       text,
  avatar_url      text,
  phone           text,
  timezone        text DEFAULT 'UTC',
  is_active       boolean NOT NULL DEFAULT true,
  last_sign_in_at timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.users IS 'Application users. Linked to Supabase Auth via auth_id.';
COMMENT ON COLUMN public.users.auth_id IS 'References auth.users.id. NULL for users created before they sign up.';
COMMENT ON COLUMN public.users.is_active IS 'Soft-delete flag. Inactive users cannot sign in.';

CREATE INDEX idx_users_org_id ON public.users(org_id);
CREATE INDEX idx_users_email ON public.users(email);
CREATE UNIQUE INDEX idx_users_auth_id ON public.users(auth_id) WHERE auth_id IS NOT NULL;

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.users
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: teams
-- Groups of users within an organization.
-- -----------------------------------------------------------------------------
CREATE TABLE public.teams (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  name            text NOT NULL,
  description     text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.teams IS 'Named groups of users within an organization (e.g. Sales, Engineering).';

CREATE INDEX idx_teams_org_id ON public.teams(org_id);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.teams
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: memberships
-- Joins users to organizations and optionally to teams.
-- This is the source of truth for access control.
-- -----------------------------------------------------------------------------
CREATE TABLE public.memberships (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  user_id         uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  team_id         uuid REFERENCES public.teams(id) ON DELETE SET NULL,
  role            public.membership_role NOT NULL DEFAULT 'member',
  status          public.membership_status NOT NULL DEFAULT 'active',
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb,
  UNIQUE(org_id, user_id)
);

COMMENT ON TABLE public.memberships IS 'Links users to orgs with a role. Source of truth for access control.';
COMMENT ON COLUMN public.memberships.team_id IS 'Optional team assignment. A user can be in an org without a team.';

CREATE INDEX idx_memberships_org_id ON public.memberships(org_id);
CREATE INDEX idx_memberships_user_id ON public.memberships(user_id);
CREATE INDEX idx_memberships_team_id ON public.memberships(team_id);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.memberships
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: roles
-- Named permission sets. Used for granular access beyond membership_role.
-- -----------------------------------------------------------------------------
CREATE TABLE public.roles (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  name            text NOT NULL,
  description     text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb,
  UNIQUE(org_id, name)
);

COMMENT ON TABLE public.roles IS 'Named permission sets for granular access control beyond membership roles.';

CREATE INDEX idx_roles_org_id ON public.roles(org_id);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.roles
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: permissions
-- Individual permissions assigned to roles.
-- -----------------------------------------------------------------------------
CREATE TABLE public.permissions (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  role_id         uuid NOT NULL REFERENCES public.roles(id) ON DELETE CASCADE,
  resource        text NOT NULL,
  action          text NOT NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb,
  UNIQUE(role_id, resource, action)
);

COMMENT ON TABLE public.permissions IS 'Individual permissions assigned to roles. Resource + action pairs (e.g. deals.update).';
COMMENT ON COLUMN public.permissions.resource IS 'The resource being controlled (e.g. deals, contacts, invoices).';
COMMENT ON COLUMN public.permissions.action IS 'The action being permitted (e.g. read, create, update, delete).';

CREATE INDEX idx_permissions_org_id ON public.permissions(org_id);
CREATE INDEX idx_permissions_role_id ON public.permissions(role_id);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.permissions
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
