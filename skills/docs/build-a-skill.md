# Build a Skill

This guide walks through creating a new skill from scratch. A skill is a self-contained directory with four files: `manifest.json`, `migration.sql`, `seed.sql`, and `SKILL.md`.

## Directory Structure

```
skills/
└── notes/
    ├── manifest.json
    ├── migration.sql
    ├── seed.sql
    └── SKILL.md
```

## Step 1: manifest.json

Declare your skill's metadata and dependencies.

```json
{
  "name": "notes",
  "version": "1.0.0",
  "description": "Simple notes attached to any entity",
  "depends_on": ["identity"],
  "tables": ["notes"],
  "author": "YourName"
}
```

- `name` -- must match the directory name
- `depends_on` -- array of skill names this skill requires (at minimum `identity`)
- `tables` -- every table your migration creates

## Step 2: migration.sql

Write a single SQL file that creates everything: enums, tables, indexes, triggers, and RLS policies.

```sql
-- notes skill: simple notes attached to any entity

CREATE TABLE public.notes (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid NOT NULL REFERENCES public.organizations(id),
  author_id   uuid NOT NULL REFERENCES public.users(id),
  entity_type text NOT NULL,
  entity_id   uuid NOT NULL,
  body        text NOT NULL,
  metadata    jsonb DEFAULT '{}',
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_notes_org ON public.notes(org_id);
CREATE INDEX idx_notes_entity ON public.notes(entity_type, entity_id);

CREATE TRIGGER trg_notes_updated_at
  BEFORE UPDATE ON public.notes
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.notes ENABLE ROW LEVEL SECURITY;

CREATE POLICY notes_select ON public.notes
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY notes_insert ON public.notes
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY notes_update ON public.notes
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY notes_delete ON public.notes
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());
```

Key rules:
- Every table must have `org_id uuid NOT NULL REFERENCES public.organizations(id)`
- Every table must have `metadata jsonb DEFAULT '{}'`
- Every table must have `created_at` and `updated_at` with the `set_updated_at()` trigger
- Every table must have RLS enabled with at least SELECT and INSERT policies
- Use `public.get_user_org_id()` for org-scoped RLS
- Use `public.is_admin()` for admin-only operations

## Step 3: seed.sql

Provide realistic demo data. Reference the shared UUIDs from `identity/seed.sql`:

- Org: `a0000000-0000-0000-0000-000000000001`
- Users: `b0000000-0000-0000-0000-00000000000X`

```sql
-- Notes seed data
BEGIN;

INSERT INTO public.notes (id, org_id, author_id, entity_type, entity_id, body) VALUES
  ('c1000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'contact', 'f2000000-0000-0000-0000-000000000001', 'Spoke at the React conference last year. Strong technical background.'),
  ('c1000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000002', 'deal', 'a3000000-0000-0000-0000-000000000001', 'Budget approved. Moving to contract stage next week.');

COMMIT;
```

## Step 4: SKILL.md

Document your skill with YAML frontmatter for CLI discoverability.

```markdown
---
name: notes
description: Simple notes attached to any entity
---

# Notes

Attach free-form notes to contacts, deals, tickets, or any other entity.

## Tables

### notes

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| org_id | uuid | Organization (tenant) |
| author_id | uuid | User who wrote the note |
| entity_type | text | Target entity type |
| entity_id | uuid | Target entity ID |
| body | text | Note content |
| metadata | jsonb | Extensibility field |
| created_at | timestamptz | Creation timestamp |
| updated_at | timestamptz | Last update timestamp |

## Dependencies

- `identity`

## Example Queries

### All notes for a contact

\```sql
SELECT n.body, u.full_name AS author, n.created_at
FROM notes n
JOIN users u ON u.id = n.author_id
WHERE n.entity_type = 'contact' AND n.entity_id = '<contact_id>'
ORDER BY n.created_at DESC;
\```
```

## Testing

After creating your skill, test it:

```bash
# Install identity first (required dependency)
./scripts/install.sh identity

# Install your skill
./scripts/install.sh notes

# Seed with demo data
./scripts/install.sh --seed notes
```

Verify that:
1. All tables are created with `\dt` in psql
2. RLS policies are active with `\dp`
3. Seed data inserts without errors
4. Queries in your SKILL.md return expected results
