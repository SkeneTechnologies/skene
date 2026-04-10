<div align="center">

# ⚡ Supabase Skills

### Stop writing the same migrations. Start building your app.

**37 tables. 11 skills. One `psql` command. Production-ready.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15%2B-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Supabase](https://img.shields.io/badge/Supabase-Ready-3ECF8E?logo=supabase&logoColor=white)](https://supabase.com)
[![GitHub Stars](https://img.shields.io/github/stars/SkeneTechnologies/skene?style=flat&label=Stars)](https://github.com/SkeneTechnologies/skene)

[Getting Started](#getting-started) · [Available Skills](#available-skills) · [Build Your Own](#build-your-own) · [Schema Design](#schema-design)

</div>

---

```bash
./scripts/install.sh --seed all
# That's it. 37 tables, RLS policies, seed data. Done.
```

---

## The Problem

You're building a SaaS app. You need users, orgs, contacts, deals, tickets, subscriptions. So you write migrations. Then RLS policies. Then seed data. Then you do it again on the next project.

**Supabase Skills gives you the backend so you can build the frontend.**

Each skill is a self-contained, composable piece of infrastructure -- install what you need, skip what you don't.

## Getting Started

```bash
git clone https://github.com/SkeneTechnologies/skene.git
cd skene/supabase-skills

export DATABASE_URL="postgresql://postgres:password@localhost:54322/postgres"

# Install just what you need (dependencies resolve automatically)
./scripts/install.sh crm

# Or go all-in
./scripts/install.sh --seed all
```

That's it. Your database now has tables, indexes, RLS policies, and demo data.

## Available Skills

<table>
<tr>
<td width="50%">

### 🔐 [identity](skills/identity/SKILL.md)
Organizations, users, teams, memberships, roles, permissions
<br><sub>6 tables · 2 enums · Foundation for everything</sub>

### 👥 [crm](skills/crm/SKILL.md)
Contacts, companies, and many-to-many relationships
<br><sub>3 tables · 1 enum · Depends on identity</sub>

### 📊 [pipeline](skills/pipeline/SKILL.md)
Pipelines, stages, deals, and full stage transition history
<br><sub>4 tables · 1 enum · Depends on crm</sub>

### ✅ [tasks](skills/tasks/SKILL.md)
Projects, tasks, and dependency tracking
<br><sub>3 tables · 2 enums · Depends on identity</sub>

### 🎫 [support](skills/support/SKILL.md)
Tickets with priority, status, channel, and SLA tracking
<br><sub>1 table · 3 enums · Depends on identity</sub>

### 💬 [comms](skills/comms/SKILL.md)
Threaded messages attachable to any entity
<br><sub>2 tables · 2 enums · Depends on crm</sub>

</td>
<td width="50%">

### 📄 [content](skills/content/SKILL.md)
Folders, documents, and nested comments
<br><sub>3 tables · 1 enum · Depends on identity</sub>

### 💳 [billing](skills/billing/SKILL.md)
Products, prices, subscriptions, invoices, payments
<br><sub>5 tables · 4 enums · Stripe-ready · Depends on crm</sub>

### 📅 [calendar](skills/calendar/SKILL.md)
Events and attendees with optional CRM links
<br><sub>2 tables · 2 enums · Depends on identity</sub>

### 🤖 [automations](skills/automations/SKILL.md)
Triggers, action sequences, and execution logs
<br><sub>3 tables · 3 enums · Depends on identity</sub>

### 📈 [analytics](skills/analytics/SKILL.md)
Tags, custom fields, and activity log for any entity
<br><sub>5 tables · 2 enums · Depends on identity</sub>

<br>

> **37 tables · 22 enums · 11 skills**
> <br>All with Row-Level Security. All multi-tenant.

</td>
</tr>
</table>

## What You Can Build

| App | Skills | You get |
|-----|--------|---------|
| **CRM** | identity + crm + pipeline + comms + analytics | Contact management, deal tracking, communication history, activity feeds |
| **Project Management** | identity + tasks + content + calendar | Projects, task boards, docs, team calendars |
| **Help Desk** | identity + crm + support + comms + analytics | Ticket queues, customer threads, SLA tracking |
| **Billing Platform** | identity + crm + billing | Subscriptions, invoices, payments, Stripe integration |
| **Everything** | `./scripts/install.sh all` | All 37 tables, full business backend |

Mix and match. Every combination gives you a working multi-tenant backend with RLS out of the box.

## What's in a Skill

Each skill is a directory with four files:

```
skills/crm/
├── manifest.json    # Dependencies and metadata
├── migration.sql    # Tables, enums, indexes, triggers, RLS policies
├── seed.sql         # Realistic demo data
└── SKILL.md         # Full docs with example queries
```

Skills declare dependencies. The install script resolves them automatically:

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

## Schema Design

Every table follows the same conventions. No exceptions.

| Convention | What it means |
|-----------|---------------|
| **Multi-tenant** | Every table has `org_id`. Every query is scoped. |
| **RLS everywhere** | Row-level security on every table. Tenant isolation enforced at the database layer. |
| **UUIDs** | `gen_random_uuid()` primary keys. No serial IDs leaking row counts. |
| **Timestamps** | `created_at` and `updated_at` on every table with an automatic trigger. |
| **JSONB escape hatch** | `metadata jsonb DEFAULT '{}'` on every table for app-specific fields, embeddings, whatever you need. |
| **Enums** | PostgreSQL enums for status fields. No unconstrained strings. |
| **Cents, not dollars** | Money stored as integer cents. No floating point math. |
| **Polymorphic refs** | `entity_type` + `entity_id` for comments, tags, activities. Attach anything to anything. |

### RLS Functions

The `identity` skill defines four helper functions every other skill uses:

```sql
get_user_org_id()   -- Returns the current user's organization ID
get_user_role()     -- Returns the current user's role (owner, admin, member)
is_admin()          -- Returns true if the user is an admin or owner
set_updated_at()    -- Trigger function for automatic updated_at
```

## AI-Ready

Point your AI coding assistant at any `SKILL.md` and it has everything it needs:

- Table definitions with every column and type
- Enum values with descriptions
- RLS policy rules
- 5+ working SQL queries per skill
- `COMMENT ON` annotations on every table and column

The `metadata` JSONB column is there for embeddings, AI-generated fields, or any structured data your LLM pipeline produces.

## Build Your Own

```
skills/notes/
├── manifest.json
├── migration.sql
├── seed.sql
└── SKILL.md
```

Four files. Follow the conventions. Declare your dependencies. That's a skill.

See [docs/build-a-skill.md](docs/build-a-skill.md) for the full guide.

## FAQ

<details>
<summary><b>Do I need all 11 skills?</b></summary>
<br>
No. Install only what you need. The minimum is <code>identity</code>, which gives you multi-tenant users and orgs. Everything else is optional.
</details>

<details>
<summary><b>Can I modify the migrations?</b></summary>
<br>
Yes. These are plain SQL files. Fork the repo, change what you need, run them against your database. There is no ORM, no code generation, no lock-in.
</details>

<details>
<summary><b>Does this work with Supabase hosted?</b></summary>
<br>
Yes. Set <code>DATABASE_URL</code> to your Supabase project's connection string and run the install script.
</details>

<details>
<summary><b>What about Supabase Auth?</b></summary>
<br>
The <code>identity</code> skill's <code>users</code> table has an <code>auth_id</code> column that references <code>auth.users(id)</code>. RLS policies use <code>auth.uid()</code> to identify the current user. Connect Supabase Auth and it works automatically.
</details>

<details>
<summary><b>Can I use this without Supabase?</b></summary>
<br>
The SQL is standard PostgreSQL. You need <code>pgcrypto</code> (for <code>gen_random_uuid()</code>) and either Supabase Auth or your own implementation of <code>auth.uid()</code>.
</details>

<details>
<summary><b>What about the shared <code>channel_type</code> enum?</b></summary>
<br>
Both <code>support</code> and <code>comms</code> use a <code>CREATE TYPE IF NOT EXISTS</code> guard. Install them in any order. The enum is created once and shared.
</details>

## Contributing

1. Fork the repo
2. Create a feature branch
3. Add or modify a skill following [docs/build-a-skill.md](docs/build-a-skill.md)
4. Open a pull request

---

<div align="center">

Built by [Skene Technologies](https://github.com/SkeneTechnologies)

[MIT License](LICENSE)

</div>
