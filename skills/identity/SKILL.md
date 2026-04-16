---
name: identity
description: Multi-tenant organizations, users, teams, memberships, roles, and permissions with RLS
---

# Identity

Foundation schema for multi-tenant Supabase applications. Provides organizations, users, teams, memberships, roles, and fine-grained permissions -- all scoped by organization with row-level security.

## Tables

### organizations

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| name | text | Organization name |
| slug | text | URL-safe unique identifier for routes and subdomains |
| logo_url | text | URL to org logo |
| domain | text | Organization domain |
| stripe_customer_id | text | Stripe customer ID for billing integration |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Last update timestamp (auto-set by trigger) |
| metadata | jsonb | Arbitrary JSON for org-level settings or feature flags |

### users

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| org_id | uuid | FK to organizations. Scopes the user to one org |
| auth_id | uuid | FK to auth.users(id). NULL for invited but unsigned-up users |
| email | text | User email address |
| full_name | text | Display name |
| avatar_url | text | URL to avatar image |
| phone | text | Phone number |
| timezone | text | User timezone, defaults to UTC |
| is_active | boolean | Soft-delete flag. Inactive users cannot sign in |
| last_sign_in_at | timestamptz | Timestamp of most recent sign-in |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Last update timestamp (auto-set by trigger) |
| metadata | jsonb | Arbitrary JSON for user-level settings |

### teams

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| org_id | uuid | FK to organizations |
| name | text | Team name |
| description | text | Team description |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Last update timestamp (auto-set by trigger) |
| metadata | jsonb | Arbitrary JSON |

### memberships

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| org_id | uuid | FK to organizations |
| user_id | uuid | FK to users |
| team_id | uuid | Optional FK to teams. NULL means org-level membership only |
| role | membership_role | Role within the org: owner, admin, member, or guest |
| status | membership_status | Membership state: active, invited, or suspended |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Last update timestamp (auto-set by trigger) |
| metadata | jsonb | Arbitrary JSON |

Unique constraint on (org_id, user_id).

### roles

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| org_id | uuid | FK to organizations |
| name | text | Role name, unique per org |
| description | text | Role description |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Last update timestamp (auto-set by trigger) |
| metadata | jsonb | Arbitrary JSON |

Unique constraint on (org_id, name).

### permissions

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| org_id | uuid | FK to organizations |
| role_id | uuid | FK to roles |
| resource | text | Dot-notated resource identifier, e.g. "projects", "billing.invoices" |
| action | text | Operation allowed on the resource, e.g. "read", "write", "delete" |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Last update timestamp (auto-set by trigger) |
| metadata | jsonb | Arbitrary JSON |

Unique constraint on (role_id, resource, action).

## Enums

### membership_role

| Value | Description |
|-------|-------------|
| owner | Full control including org deletion |
| admin | Can manage users, roles, and settings |
| member | Standard access |
| guest | Limited read access |

### membership_status

| Value | Description |
|-------|-------------|
| active | Currently active membership |
| invited | Invited but has not yet accepted |
| suspended | Temporarily disabled |

## Functions

- `set_updated_at()` -- Trigger function that sets updated_at to now() on every UPDATE.
- `get_user_org_id()` -- Returns the org_id of the currently authenticated user. Used in RLS policies.
- `get_user_role()` -- Returns the membership_role of the currently authenticated user within their org.
- `is_admin()` -- Returns true if the current user has an admin or owner role.

## Row-Level Security

All tables have RLS enabled and are scoped to the current user's organization via `get_user_org_id()`.

- **organizations**: SELECT for own org. INSERT open (for onboarding). UPDATE requires admin. DELETE requires owner.
- **users**: SELECT/INSERT for own org. UPDATE allowed for own record or admins. DELETE requires admin.
- **teams**: SELECT/INSERT/UPDATE for own org. DELETE requires admin.
- **memberships**: SELECT for own org. INSERT/DELETE requires admin. UPDATE allowed for own record or admins.
- **roles**: SELECT for own org. INSERT/UPDATE/DELETE requires admin.
- **permissions**: SELECT for own org. INSERT/UPDATE/DELETE requires admin.

## Dependencies

None. This is the foundation skill.

## Example Queries

List all active users in the current organization:

```sql
SELECT u.id, u.full_name, u.email, m.role, m.status
FROM users u
JOIN memberships m ON m.user_id = u.id AND m.org_id = u.org_id
WHERE u.org_id = get_user_org_id()
  AND u.is_active = true
  AND m.status = 'active'
ORDER BY u.full_name;
```

Get all members of a specific team:

```sql
SELECT u.full_name, u.email, m.role
FROM memberships m
JOIN users u ON u.id = m.user_id
WHERE m.team_id = '<team_id>'
  AND m.status = 'active'
ORDER BY u.full_name;
```

Find all users with a given role:

```sql
SELECT u.full_name, u.email, m.role, t.name AS team_name
FROM memberships m
JOIN users u ON u.id = m.user_id
LEFT JOIN teams t ON t.id = m.team_id
WHERE m.org_id = get_user_org_id()
  AND m.role = 'admin'
  AND m.status = 'active'
ORDER BY u.full_name;
```

Check which permissions a specific role grants:

```sql
SELECT p.resource, p.action
FROM permissions p
JOIN roles r ON r.id = p.role_id
WHERE r.org_id = get_user_org_id()
  AND r.name = '<role_name>'
ORDER BY p.resource, p.action;
```

Get organization details with total member count:

```sql
SELECT
  o.name,
  o.slug,
  o.domain,
  count(m.id) AS member_count
FROM organizations o
LEFT JOIN memberships m ON m.org_id = o.id AND m.status = 'active'
WHERE o.id = get_user_org_id()
GROUP BY o.id, o.name, o.slug, o.domain;
```
