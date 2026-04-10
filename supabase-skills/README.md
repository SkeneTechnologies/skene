# Supabase Skills

Ready-made Supabase schemas for business apps. Pick the skills you need, run the SQL, start building.

```
npx supabase db reset
psql $DATABASE_URL -f skills/identity/migration.sql
psql $DATABASE_URL -f skills/crm/migration.sql
psql $DATABASE_URL -f skills/pipeline/migration.sql
# ... or just run ./scripts/install.sh all
```

## Why

Every SaaS app needs the same tables: users, contacts, deals, tickets, subscriptions. You end up writing the same migrations, the same RLS policies, the same seed data -- over and over.

Supabase Skills gives you production-ready schemas so you can skip the boilerplate and start building features on day one.

## What is a skill

A skill is a self-contained backend capability. Each skill is a directory with four files:

```
skills/crm/
├── manifest.json    # metadata and dependencies
├── migration.sql    # tables, enums, indexes, RLS policies
├── seed.sql         # demo data for development
└── SKILL.md         # documentation and example queries
```

Skills declare their dependencies in `manifest.json`. When you install a skill, its dependencies are resolved and installed first.

## Available Skills

| Skill | Tables | Description |
|-------|--------|-------------|
| [identity](skills/identity/SKILL.md) | 6 | Organizations, users, teams, memberships, roles, permissions |
| [crm](skills/crm/SKILL.md) | 3 | Contacts, companies, and relationships |
| [pipeline](skills/pipeline/SKILL.md) | 4 | Pipelines, stages, deals, and stage history |
| [tasks](skills/tasks/SKILL.md) | 3 | Projects, tasks, and dependencies |
| [support](skills/support/SKILL.md) | 1 | Tickets with priority, status, and channel tracking |
| [comms](skills/comms/SKILL.md) | 2 | Threads and messages for any entity |
| [content](skills/content/SKILL.md) | 3 | Folders, documents, and comments |
| [billing](skills/billing/SKILL.md) | 5 | Products, prices, subscriptions, invoices, payments |
| [calendar](skills/calendar/SKILL.md) | 2 | Events and attendees |
| [automations](skills/automations/SKILL.md) | 3 | Triggers, actions, and execution logs |
| [analytics](skills/analytics/SKILL.md) | 5 | Tags, custom fields, and activity log |

**37 tables** across **11 skills**.

## What You Can Build

- **CRM** -- identity + crm + pipeline + comms + analytics
- **Project management tool** -- identity + tasks + content + calendar
- **Help desk** -- identity + crm + support + comms + analytics
- **Subscription billing platform** -- identity + crm + billing
- **All of the above** -- install everything with `./scripts/install.sh all`

Mix and match. Each combination gives you a working multi-tenant backend with RLS out of the box.

## How It Works

### Install

```bash
# Clone the repo
git clone https://github.com/SkeneTechnologies/skene.git
cd skene/supabase-skills

# Set your database URL
export DATABASE_URL="postgresql://postgres:password@localhost:54322/postgres"

# Install specific skills (dependencies resolved automatically)
./scripts/install.sh crm

# Or install everything
./scripts/install.sh all

# Install with seed data
./scripts/install.sh --seed all
```

### Reset

```bash
# Drop all tables and reinstall
./scripts/reset.sh

# Drop, reinstall, and re-seed
./scripts/reset.sh --seed
```

### Manual install

If you prefer to run migrations directly:

```bash
# Identity must come first
psql $DATABASE_URL -f skills/identity/migration.sql

# Then any skills that depend on identity
psql $DATABASE_URL -f skills/crm/migration.sql
psql $DATABASE_URL -f skills/pipeline/migration.sql

# Seed data (optional)
psql $DATABASE_URL -f skills/identity/seed.sql
psql $DATABASE_URL -f skills/crm/seed.sql
psql $DATABASE_URL -f skills/pipeline/seed.sql
```

## Schema Design

Every table follows the same conventions:

- **Multi-tenant by default** -- every table has `org_id` scoped to an organization
- **RLS on every table** -- row-level security policies enforce tenant isolation
- **UUIDs everywhere** -- `gen_random_uuid()` as default primary keys
- **Timestamps** -- `created_at` and `updated_at` on every table, with an automatic trigger
- **Soft extensibility** -- `metadata jsonb DEFAULT '{}'` on every table for app-specific fields
- **Enums for status fields** -- PostgreSQL enums instead of unconstrained text
- **Integer cents for money** -- `value` and `amount` columns store cents, not dollars
- **Polymorphic references** -- `entity_type` + `entity_id` pairs for comments, tags, activities

### RLS Functions

The `identity` skill defines four helper functions used by all RLS policies:

| Function | Returns | Purpose |
|----------|---------|---------|
| `get_user_org_id()` | uuid | Current user's organization ID |
| `get_user_role()` | membership_role | Current user's role in their org |
| `is_admin()` | boolean | Whether current user is an admin or owner |
| `set_updated_at()` | trigger | Automatically sets `updated_at` on row update |

### Dependency Graph

```
identity
├── crm
│   ├── pipeline
│   ├── comms
│   └── billing
├── tasks
├── support
├── content
├── calendar
├── automations
└── analytics
```

See [docs/dependencies.md](docs/dependencies.md) for the full dependency table.

## AI-Ready

The schema is designed to work well with AI-powered development tools. Every table has:

- Descriptive column names that read like natural language
- `COMMENT ON` annotations for each table and column
- Consistent naming conventions across all skills
- A `metadata` JSONB column for storing embeddings, AI-generated fields, or any structured data

Point your AI coding assistant at a SKILL.md file and it has everything it needs: table definitions, enum values, RLS rules, and working SQL examples.

## Build Your Own

Want to add a skill? See [docs/build-a-skill.md](docs/build-a-skill.md) for a step-by-step guide.

The short version:

1. Create a directory under `skills/` with four files: `manifest.json`, `migration.sql`, `seed.sql`, `SKILL.md`
2. Follow the schema conventions (org_id, metadata, timestamps, RLS)
3. Declare dependencies in `manifest.json`
4. Add example queries to your SKILL.md

## FAQ

**Do I need all 11 skills?**
No. Install only what you need. The minimum is `identity`, which gives you multi-tenant users and orgs.

**Can I modify the migrations?**
Yes. These are plain SQL files. Fork the repo, change what you need, run them against your database.

**Does this work with Supabase hosted?**
Yes. Set `DATABASE_URL` to your Supabase project's connection string and run the install script.

**What about Supabase Auth?**
The `identity` skill's `users` table has an `auth_id` column that references `auth.users(id)`. RLS policies use `auth.uid()` to identify the current user. Connect Supabase Auth and it works automatically.

**How do I handle the `channel_type` enum shared between support and comms?**
Both skills use a `CREATE TYPE IF NOT EXISTS` guard, so they work in any install order. If you install both, the enum is created once and shared.

**Can I use this without Supabase?**
The SQL is standard PostgreSQL. You need the `pgcrypto` extension (for `gen_random_uuid()`) and either Supabase Auth or your own implementation of `auth.uid()`.

## Contributing

1. Fork the repo
2. Create a feature branch
3. Add or modify a skill following the conventions in [docs/build-a-skill.md](docs/build-a-skill.md)
4. Open a pull request

## Built by Skene

Supabase Skills is built and maintained by [Skene Technologies](https://github.com/SkeneTechnologies). We use these schemas in production to power our own products.

## License

[MIT](LICENSE)
