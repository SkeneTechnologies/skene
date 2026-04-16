<p align="center">
  <img src="https://skene.ai/img/skene-logo.svg" alt="Skene" width="140" />
</p>

<h3 align="center">Backend skills for your Supabase</h3>

<p align="center">
  <a href="#why-this-exists">Why</a> &middot;
  <a href="#quick-start">Quick Start</a> &middot;
  <a href="#available-skills">Available Skills</a> &middot;
  <a href="#built-for-ai-agents">AI Agents</a> &middot;
  <a href="#skene-cloud-optional">Skene Cloud</a> &middot;
  <a href="docs/dependencies.md">Dependencies</a>
</p>

<p align="center">
  <a href="https://www.npmjs.com/package/@skene/database-skills"><img src="https://img.shields.io/npm/v/@skene/database-skills?label=npm&color=CB3837&logo=npm" alt="npm" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License" /></a>
  <a href="https://supabase.com"><img src="https://img.shields.io/badge/Supabase-ready-3ECF8E?logo=supabase&logoColor=white" alt="Supabase Ready" /></a>
  <a href="https://skills.sh"><img src="https://img.shields.io/badge/skills.sh-compatible-000000" alt="skills.sh" /></a>
  <a href="https://skene.ai"><img src="https://img.shields.io/badge/Skene_Cloud-compatible-E8C260" alt="Skene Cloud" /></a>
</p>

---

Install backend Skills into your Supabase project. CRM, billing, helpdesk, project management, calendar, and more. Each Skill adds tables, enums, RLS policies, and seed data. Pick what you need.

```bash
npx @skene/database-skills init
```

One command. Installs the package, configures your AI tools, detects Supabase MCP. Your next agent session sets up the database automatically.

The same data model that powers Salesforce, HubSpot, Jira, Zendesk, and Stripe. Except you own it.

<p align="center">
  <img src="docs/assets/skene-engine-demo.gif" alt="Skene Database Skills" width="720" />
</p>

---

## Why this exists

AI can build a frontend in minutes. Cursor, Claude Code, v0, Bolt -- they generate UI fast. But every project still starts with an empty Postgres instance and a blank migration file.

Every founder using AI to build a SaaS product hits the same wall in the first hour. What tables do I need? How do I handle multi-tenancy? What should my RLS look like?

These are solved problems. But everyone solves them alone, from scratch, every time.

### Skene Skills are the starting line

Composable backend capabilities you install and build on.

Every business app stores the same data. CRM, helpdesk, project management, billing -- 80% of the schema is identical. That 80% should not be custom work every time.

### Your AI agent gets a 2-week head start

An agent building on a well-defined, documented schema writes better code with fewer tokens than one guessing your data model. Less prompting, more building.

### Your data is becoming someone else's moat

In 2025, the platforms you pay to store your business data started locking it down. Salesforce [changed its Slack API terms](https://www.computerworld.com/article/4005509/salesforce-changes-slack-api-terms-to-block-bulk-data-access-for-llms.html) to prohibit bulk data export and explicitly block using data accessed via Slack APIs to train LLMs. Third-party AI tools that had been indexing Slack conversations to build internal copilots were cut off overnight.

Meta updated its WhatsApp Business terms to prohibit third-party AI providers from using the API if AI is their primary service, prompting the [European Commission to open a formal antitrust investigation](https://ec.europa.eu/commission/presscorner/detail/en/ip_25_2896) and [Italy's antitrust authority to force Meta to suspend the restrictive terms](https://en.agcm.it/en/media/press-releases/2025/12/A576).

The pattern is the same everywhere. You store data in a vendor's system. The vendor decides you can't use that data to train your own AI, feed it to a competitor's model, or even export it without restrictions. Your CRM data, your support tickets, your team conversations -- all behind someone else's API, subject to terms they can change whenever they want.

### You own the data

Skene Skills deploy directly into your Supabase Postgres instance. No per-seat pricing. No rate-limited APIs. No Zapier glue between tools. One database you control. When you want to train an AI on your customer data, query it from your own tables, or pipe it into whatever model you choose, nobody can change the terms on you. The data is yours because the database is yours.

---

## Quick start

### 1. Run init

```bash
npx @skene/database-skills init
```

This does three things:
- Installs the package in your project
- Configures your AI tools (Claude Code, Cursor, Windsurf, Copilot, Cline)
- Detects Supabase MCP and environment keys

### 2. Open your AI agent

Your agent reads the config, discovers the skill, and asks what you're building:

| Preset | Skills |
|--------|--------|
| `crm` | identity, crm, pipeline, comms, analytics |
| `helpdesk` | identity, crm, support, comms, content, knowledge, analytics |
| `billing` | identity, crm, billing, commerce, analytics |
| `project` | identity, tasks, content, calendar, analytics |
| `marketing` | identity, crm, campaigns, forms, analytics |
| `full` | all 19 skills |

The agent applies the schema to your Supabase project via MCP — no connection string needed.

### Alternative: CLI without an agent

```bash
npx @skene/database-skills crm --db $DATABASE_URL --seed
```

Resolves dependencies, applies migrations, loads demo data. Pass comma-separated skill names for custom combinations: `npx @skene/database-skills crm,pipeline,support`

### Or via skills.sh

```bash
# Install all Skene Skills
npx skills add https://github.com/SkeneTechnologies/skene/tree/main/skills

# Or install specific skills
npx skills add https://github.com/SkeneTechnologies/skene/tree/main/skills -s crm
npx skills add https://github.com/SkeneTechnologies/skene/tree/main/skills -s billing
```

Skills install to `.claude/skills/` (or the equivalent directory for your AI agent). Each skill includes a `SKILL.md` with full schema documentation, example queries, and a `migration.sql` your agent applies to Supabase.

### Or apply migrations directly

No agent needed. Run the SQL files against your Supabase project:

```bash
psql "$DATABASE_URL" -f identity/migration.sql
psql "$DATABASE_URL" -f crm/migration.sql
psql "$DATABASE_URL" -f pipeline/migration.sql
```

### Load demo data (optional)

Each skill includes a `seed.sql` with realistic sample data:

```bash
psql "$DATABASE_URL" -f identity/seed.sql
psql "$DATABASE_URL" -f crm/seed.sql
```

Creates fictional data you can build against immediately -- contacts, companies, deals, tickets, billing, and activity records.

---

## Available Skills

| Skill | What it adds to your Supabase project | Depends on |
|-------|---------------------------------------|------------|
| `identity` | Organizations, users, teams, roles, permissions | none |
| `crm` | Contacts, companies, relationships | identity |
| `pipeline` | Deals, stages, stage history | crm |
| `tasks` | Projects, tasks, dependencies | identity |
| `support` | Tickets with priorities, SLAs, channels | crm |
| `comms` | Threads and messages for any entity | crm |
| `content` | Folders, documents, comments | identity |
| `billing` | Products, prices, subscriptions, invoices, payments (Stripe-ready) | crm |
| `calendar` | Events and attendees | identity |
| `automations` | Triggers, actions, execution logs | identity |
| `analytics` | Tags, custom fields, activity log | identity |
| `forms` | Form definitions, fields, submissions, file uploads | identity |
| `notifications` | Templates, delivery log, preferences, push tokens | identity |
| `campaigns` | Email campaigns, segments, lists, engagement tracking | crm |
| `commerce` | Orders, carts, shipping, fulfillment | billing |
| `knowledge` | Articles, categories, publish status | content |
| `approvals` | Approval chains, requests, decisions, delegation | identity |
| `integrations` | Connected apps, OAuth tokens, webhooks, sync logs | identity |
| `compliance` | Consent records, deletion requests, retention policies | identity |

**19 Skills. ~72 tables. All with RLS. All multi-tenant.**

### Dependency tree

```
identity
├── crm
│   ├── pipeline
│   ├── support
│   ├── comms
│   ├── billing
│   │   └── commerce
│   └── campaigns
├── tasks
├── content
│   └── knowledge
├── calendar
├── automations
├── analytics
├── forms
├── notifications
├── approvals
├── integrations
└── compliance
```

Every table gets:

- `id` uuid primary key
- `org_id` for multi-tenant isolation
- `created_at` / `updated_at` with automatic triggers
- `metadata` jsonb escape hatch
- Row Level Security enforced

---

## Built-in lifecycles

Every skill with a status enum defines a lifecycle your app can track:

| Lifecycle | Stages | Source |
|-----------|--------|--------|
| Contact | lead → prospect → customer → partner | `contact_type` enum |
| Deal | per-pipeline custom stages | `pipeline_stages` table |
| Ticket | open → pending → resolved → closed | `ticket_status` enum |
| Subscription | trialing → active → past_due → canceled | `subscription_status` enum |
| Task | todo → in_progress → in_review → done | `task_status` enum |
| Invoice | draft → open → paid → void | `invoice_status` enum |
| Document | draft → published → archived | `document_status` enum |

---

## Built for AI agents

Skene Skills follow the [Agent Skills](https://agentskills.io) open standard. Each skill includes a `SKILL.md` that any AI coding agent can read -- Claude Code, Cursor, GitHub Copilot, Gemini CLI, and others.

When you install via `npx skills add`, the SKILL.md files land in your agent's skills directory. Your agent gets full context: table schemas, column types, enums, RLS rules, and working SQL examples. No weeks of migration iteration.

The schema uses consistent patterns that AI agents understand immediately:

- Every table has the same base columns (`id`, `org_id`, `created_at`, `updated_at`, `metadata`)
- Postgres enums define clear state machines (`deal_status`, `ticket_status`, `task_status`)
- `COMMENT ON` annotations explain every table and non-obvious column
- Each SKILL.md includes example queries an agent can reference
- Dependency declarations so an agent knows what to keep or drop

**Example prompts that work out of the box:**

> Build me a CRM dashboard with Next.js. I have Skene Skills installed -- use the contacts, companies, and pipeline tables.

> Create an API with Supabase Edge Functions for managing tickets. Include status transitions and SLA tracking.

> Build a billing admin panel that shows MRR, active subscriptions, and outstanding invoices.

> Add a customer portal where contacts can view their tickets, invoices, and upcoming events.

The SKILL.md gives the agent everything it needs: typed tables, clear relationships, sensible defaults, and enough structure to generate working code without ambiguity.

---

## What you can build

Mix and match Skills. Each combination is a product:

```
CRM            = identity + crm + pipeline + comms + analytics
Project tool   = identity + tasks + content + calendar + analytics
Helpdesk       = identity + crm + support + comms + content + knowledge + analytics
Billing app    = identity + crm + billing + commerce + analytics
Marketing      = identity + crm + campaigns + forms + analytics
Internal wiki  = identity + content + knowledge
Full business  = install all 19 skills
```

Every Skill is optional except Identity. Dependencies resolve automatically.

---

## Schema design principles

**Multi-tenant by default.** Every row belongs to an org. RLS enforces isolation automatically.

**Enums for state machines.** `deal_status`, `ticket_status`, `task_status`, `subscription_status` are all Postgres enums. They define the lifecycle of every entity.

**Polymorphic references.** Tables like `activities`, `comments`, `threads`, and `taggings` use `entity_type` + `entity_id` to reference any table. One activity log covers everything.

**JSONB escape hatch.** The `metadata` column on every table lets you store unstructured data without migrations. Use it for integrations, prototyping, or fields you haven't decided on yet.

**Stripe-ready.** Nullable `stripe_*` columns on billing tables. Wire them up when you integrate Stripe. Ignore them until then. Partial unique indexes prevent duplicate Stripe IDs.

**Immutable history.** `deal_stage_history` and `activities` are append-only audit logs. Pipeline analytics and compliance for free.

---

## Skene Cloud (optional)

Skene Skills is complete on its own. When you're ready for automation, [Skene Cloud](https://skene.ai) adds a journey engine that watches your tables for changes and triggers actions (emails, webhooks, analytics events) at each lifecycle transition. Connect your Supabase project, and it reads your enums and foreign keys to map lifecycles automatically.

Your schema stays in your database. Disconnect at any time and keep everything. [Learn more →](https://skene.ai)

---

## How installation works

### What's in each Skill

```
crm/
├── SKILL.md          # Schema docs, example queries, dependencies
├── migration.sql     # Tables, enums, indexes, RLS policies
├── seed.sql          # Realistic demo data
└── manifest.json     # Metadata and dependency declarations
```

### Set up AI tool configs

```bash
npx @skene/database-skills init
```

Installs the package and configures your AI coding tools (Claude Code, Cursor, Windsurf, Copilot, Cline) so agents discover the skill automatically. Detects Supabase MCP and environment keys.

### Setup script

```bash
npx @skene/database-skills crm --db $DATABASE_URL --seed
```

Resolves dependencies, applies migrations. Run without args for interactive prompts. No `psql` required.

### Via skills.sh

```bash
# Install all skills -- lands in .claude/skills/
npx skills add https://github.com/SkeneTechnologies/skene/tree/main/skills

# Install specific skills
npx skills add https://github.com/SkeneTechnologies/skene/tree/main/skills -s crm
npx skills add https://github.com/SkeneTechnologies/skene/tree/main/skills -s billing

# Install globally (available in all projects)
npx skills add https://github.com/SkeneTechnologies/skene/tree/main/skills -g
```

Your AI agent reads the SKILL.md files for context, then applies the `migration.sql` to your Supabase project. Dependencies are declared in each skill's manifest.

### Direct SQL (no agent needed)

```bash
# Set your Supabase database URL
export DATABASE_URL="postgresql://postgres:password@db.yourproject.supabase.co:5432/postgres"

# Install skills in dependency order
psql "$DATABASE_URL" -f identity/migration.sql
psql "$DATABASE_URL" -f crm/migration.sql
psql "$DATABASE_URL" -f pipeline/migration.sql

# Optional: load seed data
psql "$DATABASE_URL" -f identity/seed.sql
psql "$DATABASE_URL" -f crm/seed.sql
```

Migrations are additive -- they create new tables and enums in the `public` schema without touching existing tables.

### Verify

```sql
-- Check RLS is enabled on all tables
SELECT tablename, rowsecurity FROM pg_tables
WHERE schemaname = 'public'
  AND tablename NOT LIKE 'pg_%';

-- List all enums
SELECT t.typname, e.enumlabel
FROM pg_type t
JOIN pg_enum e ON t.oid = e.enumtypid
ORDER BY t.typname, e.enumsortorder;
```

### Wire up Supabase Auth

The `users` table links to Supabase Auth via `auth_id`. Add this trigger to auto-create a user row on signup:

```sql
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger AS $$
BEGIN
  INSERT INTO public.users (auth_id, email, full_name, org_id)
  VALUES (
    NEW.id,
    NEW.email,
    coalesce(NEW.raw_user_meta_data->>'full_name', NEW.email),
    coalesce(
      (NEW.raw_user_meta_data->>'org_id')::uuid,
      (SELECT id FROM public.organizations LIMIT 1)
    )
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
```

---

## Why not Salesforce/HubSpot?

| | Salesforce/HubSpot | Skene Skills |
|---|---|---|
| **Data ownership** | Their servers, their rules, their API limits | Your Supabase project, your Postgres, your data |
| **AI/ML access** | Restricted. Salesforce prohibits using Slack data for LLM training. Meta blocks third-party AI on WhatsApp Business data | Full access. Train models, build features, pipe into any tool |
| **Terms stability** | Can change terms to restrict AI use, export, or integrations at any time | MIT licensed. Terms never change |
| **Pricing** | Per-seat. $25-300/user/month | Supabase pricing. $25/month for most projects |
| **Customization** | Point-and-click config, proprietary scripting | Raw SQL. Extend with Edge Functions, Realtime, Storage |
| **Vendor lock-in** | Years of migration work to leave | `pg_dump` and you're done |
| **Schema access** | Abstracted behind proprietary ORM | Direct Postgres. Every tool in the ecosystem works |
| **Open source** | No | Yes. MIT licensed. Fork it, modify it, ship it |

---

## FAQ

**What are Skills?**
Skills are composable backend capabilities that follow the [Agent Skills](https://agentskills.io) open standard. Each skill is a self-contained set of tables, enums, RLS policies, and seed data packaged with a SKILL.md that any AI agent can read. Install via [skills.sh](https://skills.sh) or apply the SQL directly.

**Do I need a CLI?**
No. Run `npx @skene/database-skills init` to set everything up. Your AI agent handles the rest via Supabase MCP. Or run the `migration.sql` files directly with `psql`. No build step, no runtime.

**Do I need psql?**
No. The setup wizard (`npx @skene/database-skills`) connects directly to your database using Node.js. `psql` is only needed if you prefer to run migration files manually.

**Can I install just one skill?**
Yes. Only `identity` is required as a base. Everything else is optional. Dependencies are declared in each skill's `manifest.json`.

**Why not EAV (Entity-Attribute-Value)?**
Real typed tables for the 80% case. JSONB `metadata` column plus `custom_field_definitions` / `custom_field_values` for the 20%. Query performance and type safety where it matters, flexibility where you need it.

**What about the UI?**
Skene Skills is the backend. Pair with any frontend framework, admin panel builder, or let an AI coding agent build the UI. The tables are designed to be straightforward to query from any client.

**Does this work without Skene Cloud?**
Yes, 100% standalone. No dependencies on Skene services. Skene Cloud adds automation and journey tracking, but Skene Skills is a complete backend on its own.

**Can I modify a skill after installing?**
Yes. It's just SQL in your Supabase project. No ORM, no code generation, no lock-in.

**Does this work without Supabase?**
The SQL is standard PostgreSQL. RLS policies and `auth.uid()` are Supabase-specific, but you can replace `auth.uid()` with your own auth layer.

---

## Contributing

PRs welcome. Each Skill needs:

- `SKILL.md` -- schema docs, example queries, dependency list (follows the [Agent Skills](https://agentskills.io) standard)
- `migration.sql` -- tables, enums, indexes, RLS policies
- `seed.sql` -- realistic demo data
- `manifest.json` -- metadata and dependency declarations

Schema conventions:

- Base columns on every table (`id`, `org_id`, `created_at`, `updated_at`, `metadata`)
- Postgres enums for status/type fields
- `COMMENT ON` for tables and non-obvious columns
- Indexes on `org_id` and frequently filtered columns
- RLS policies scoped to `get_user_org_id()`

---

## License

MIT

---

<p align="center">
  Built by <a href="https://skene.ai">Skene</a>
</p>
