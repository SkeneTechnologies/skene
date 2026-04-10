<p align="center">
  <img src="https://skene.ai/img/skene-logo.svg" alt="Skene" width="140" />
</p>

<h1 align="center">Skene DB</h1>

<p align="center">
  <strong>Every business app is just a database. This is that database.</strong>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> &middot;
  <a href="#whats-in-the-box">What's Inside</a> &middot;
  <a href="#built-for-ai-agents">AI Agents</a> &middot;
  <a href="#skene-cloud-optional-upgrade">Skene Cloud</a> &middot;
  <a href="docs/demo-walkthrough.md">Demo</a> &middot;
  <a href="docs/modules.md">Modules</a> &middot;
  <a href="docs/examples.md">Queries</a>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License" /></a>
  <a href="https://supabase.com"><img src="https://img.shields.io/badge/Supabase-ready-3ECF8E?logo=supabase&logoColor=white" alt="Supabase Ready" /></a>
  <a href="https://skene.ai"><img src="https://img.shields.io/badge/Skene_Cloud-compatible-E8C260" alt="Skene Cloud" /></a>
</p>

---

One `supabase db push` gives your project the backend for a CRM, project manager, helpdesk, billing system, calendar, and more. 37 tables. Row Level Security. Multi-tenant from day one.

```bash
git clone https://github.com/skene-ai/skene-db.git
cd skene-db
supabase link --project-ref <your-project-ref>
supabase db push
```

That's it. Your Supabase project now has the same data model that powers Salesforce, HubSpot, Jira, Zendesk, and Stripe. Except you own it.

---

## Why this exists

Every SaaS rebuilds the same tables. Contacts, companies, deals, tickets, tasks, invoices. The schema is never the hard part, but it takes weeks to get right: foreign keys, indexes, enums, RLS policies, multi-tenancy, audit logs.

Skene DB is the schema you'd write if you had unlimited time. Pre-built, tested, and ready to extend.

### Your data. Your database. Your rules.

Salesforce, HubSpot, and other SaaS platforms lock your business data behind proprietary APIs. They restrict how you can access, export, and use your own data. Some explicitly prohibit using your data to train AI models or build competing products.

With Skene DB, your data lives in your Supabase project. You own it completely. Query it with raw SQL. Pipe it into your AI models. Build whatever you want on top. No vendor lock-in, no per-seat pricing, no API rate limits on your own data.

---

## Quick start

### Option 1: Clone and push

```bash
git clone https://github.com/skene-ai/skene-db.git
cd skene-db
supabase link --project-ref <your-project-ref>
supabase db push
```

### Option 2: Prompt an AI agent

Give your AI coding agent this prompt:

> Add the Skene DB schema to my Supabase project. Clone https://github.com/skene-ai/skene-db
> and push the migrations. Then create a trigger on auth.users to auto-create a users row on signup.

The schema is designed to be readable by AI agents. Typed tables, clear naming, `COMMENT ON` annotations on every table, and example queries in [docs/examples.md](docs/examples.md). An AI agent can scaffold a full app on top of this schema from a single prompt.

### Load demo data (optional)

```bash
psql "$DATABASE_URL" -f seed/demo.sql
```

Creates a fictional company "Acme Corp" with 5 users, 20 contacts, 8 companies, 5 deals, 10 tasks, 5 tickets, billing data, and 30+ activity records spread across the last 90 days.

---

## What's in the box

```
+-------------------------------------------------------------------+
|                           SKENE DB                                 |
|                                                                    |
|  IDENTITY          CRM               PIPELINE                     |
|  organizations     contacts          pipelines                    |
|  users             companies         pipeline_stages              |
|  teams             contact_companies deals                        |
|  memberships                         deal_stage_history           |
|                                                                    |
|  TASKS             SUPPORT           COMMS                        |
|  projects          tickets           threads                      |
|  tasks                               messages                     |
|  task_dependencies                                                |
|                                                                    |
|  CONTENT           BILLING           CALENDAR                     |
|  folders           products          events                       |
|  documents         prices            event_attendees              |
|  comments          subscriptions                                  |
|                    invoices                                        |
|                    payments                                        |
|                                                                    |
|  AUTOMATIONS       FLEXIBLE DATA     ACTIVITY                     |
|  automations       tags              activities                   |
|  automation_actions taggings                                      |
|  automation_runs   custom_fields     (audit log for free)         |
|                                                                    |
|  PERMISSIONS: roles + RLS on every table                          |
+-------------------------------------------------------------------+
```

37 tables across 12 modules. Every table gets:

- `id` uuid primary key
- `org_id` for multi-tenant isolation
- `created_at` / `updated_at` with automatic triggers
- `metadata` jsonb escape hatch
- Row Level Security enforced

---

## Built for AI agents

Skene DB is designed to be the starting point for AI-assisted development. The schema uses consistent patterns that AI coding agents understand immediately:

- Every table has the same base columns (`id`, `org_id`, `created_at`, `updated_at`, `metadata`)
- Postgres enums define clear state machines (`deal_status`, `ticket_status`, `task_status`)
- `COMMENT ON` annotations explain every table and non-obvious column
- [Example queries](docs/examples.md) show common operations an agent can reference
- [Module docs](docs/modules.md) explain dependencies so an agent knows what to keep or drop

**Example prompts that work out of the box:**

> Build me a CRM dashboard with Next.js on top of the Skene DB schema. Show contacts, companies, and a deal pipeline board.

> Create an API with Supabase Edge Functions for managing tickets. Include status transitions and SLA tracking.

> Build a billing admin panel that shows MRR, active subscriptions, and outstanding invoices. Use the Skene DB billing tables.

> Add a customer portal where contacts can view their tickets, invoices, and upcoming events.

The schema gives the agent everything it needs: typed tables, clear relationships, sensible defaults, and enough structure to generate working code without ambiguity.

---

## What you can build

Mix and match modules. Each combination is a product:

| Product | Modules |
|---------|---------|
| **CRM** | contacts + companies + deals + pipeline + activities + messages |
| **Project management** | projects + tasks + dependencies + comments + activities |
| **Helpdesk** | tickets + contacts + messages + comments + activities |
| **Billing dashboard** | products + prices + subscriptions + invoices + payments |
| **Internal wiki** | documents + folders + comments + tags |
| **Scheduling tool** | events + attendees + contacts |
| **All of the above** | That's the point. |

Every module is optional except Identity. Drop what you don't need. See [docs/modules.md](docs/modules.md) for the dependency graph.

---

## Schema design principles

**Multi-tenant by default.** Every row belongs to an org. RLS enforces isolation automatically.

**Enums for state machines.** `deal_status`, `ticket_status`, `task_status`, `subscription_status` are all Postgres enums. They define the lifecycle of every entity.

**Polymorphic references.** Tables like `activities`, `comments`, `threads`, and `taggings` use `entity_type` + `entity_id` to reference any table. One activity log covers everything.

**JSONB escape hatch.** The `metadata` column on every table lets you store unstructured data without migrations. Use it for integrations, prototyping, or fields you haven't decided on yet.

**Stripe-ready.** Nullable `stripe_*` columns on billing tables. Wire them up when you integrate Stripe. Ignore them until then. Partial unique indexes prevent duplicate Stripe IDs.

**Immutable history.** `deal_stage_history` and `activities` are append-only audit logs. Pipeline analytics and compliance for free.

---

## Table overview

<details>
<summary><strong>Identity and access</strong> (6 tables)</summary>

| Table | Purpose |
|-------|---------|
| `organizations` | Root tenant. Every row in every table belongs to one. |
| `users` | Application users linked to Supabase Auth via `auth_id`. |
| `teams` | Named groups (Sales, Engineering, Support). |
| `memberships` | Joins users to orgs with a role (owner, admin, member, guest). |
| `roles` | Named permission sets for granular access control. |
| `permissions` | Resource + action pairs assigned to roles. |

</details>

<details>
<summary><strong>CRM</strong> (3 tables)</summary>

| Table | Purpose |
|-------|---------|
| `contacts` | People you do business with. Lifecycle stage, source, owner. |
| `companies` | External organizations. Industry, size, revenue. |
| `contact_companies` | Many-to-many link with title and tenure. |

</details>

<details>
<summary><strong>Pipeline</strong> (4 tables)</summary>

| Table | Purpose |
|-------|---------|
| `pipelines` | Named workflows (Sales, Recruiting, etc). |
| `pipeline_stages` | Ordered stages within a pipeline. |
| `deals` | Opportunities with value, status, and current stage. |
| `deal_stage_history` | Immutable log of every stage transition. |

</details>

<details>
<summary><strong>Tasks and projects</strong> (3 tables)</summary>

| Table | Purpose |
|-------|---------|
| `projects` | Containers for related tasks. |
| `tasks` | Work items with status, priority, assignee. |
| `task_dependencies` | Blocking relationships between tasks. |

</details>

<details>
<summary><strong>Support</strong> (1 table)</summary>

| Table | Purpose |
|-------|---------|
| `tickets` | Support requests with status, priority, channel, SLA timestamps. |

</details>

<details>
<summary><strong>Communications</strong> (2 tables)</summary>

| Table | Purpose |
|-------|---------|
| `threads` | Conversation threads attached to any entity. |
| `messages` | Individual messages (inbound, outbound, internal). |

</details>

<details>
<summary><strong>Content</strong> (3 tables)</summary>

| Table | Purpose |
|-------|---------|
| `folders` | Hierarchical folder structure. |
| `documents` | Wiki pages, notes, file references. |
| `comments` | Polymorphic comments on any entity. Threaded replies. |

</details>

<details>
<summary><strong>Billing</strong> (5 tables)</summary>

| Table | Purpose |
|-------|---------|
| `products` | Things you sell. Syncs with Stripe. |
| `prices` | Monthly, annual, or one-time pricing. |
| `subscriptions` | Active subscriptions with period and status tracking. |
| `invoices` | Billing documents with line-item totals. |
| `payments` | Individual payment transactions. |

</details>

<details>
<summary><strong>Calendar</strong> (2 tables)</summary>

| Table | Purpose |
|-------|---------|
| `events` | Calendar events with optional entity link. |
| `event_attendees` | Users or contacts attending events. |

</details>

<details>
<summary><strong>Automations</strong> (3 tables)</summary>

| Table | Purpose |
|-------|---------|
| `automations` | Automation definitions with trigger type and config. |
| `automation_actions` | Ordered steps within an automation. |
| `automation_runs` | Execution log with status and results. |

</details>

<details>
<summary><strong>Flexible data</strong> (4 tables)</summary>

| Table | Purpose |
|-------|---------|
| `tags` | Org-scoped labels. |
| `taggings` | Polymorphic join applying tags to any entity. |
| `custom_field_definitions` | Defines typed custom fields per entity type. |
| `custom_field_values` | Stores actual values with typed columns. |

</details>

<details>
<summary><strong>Activity log</strong> (1 table)</summary>

| Table | Purpose |
|-------|---------|
| `activities` | Polymorphic audit log. Every significant action gets a row. |

</details>

---

## Skene Cloud (optional upgrade)

Skene DB is complete on its own. Build your app, query with SQL, extend however you want.

When you're ready for automation, [Skene Cloud](https://skene.ai) adds a journey engine on top. It watches your Skene DB tables for changes and triggers actions automatically. No code changes required.

### How it works

```
+-----------+       +-------------------+       +------------------+
|  Your App |       |    Skene DB       |       |   Skene Cloud    |
|           | ----> |  (your Supabase)  | ----> |   (skene.ai)     |
|  Frontend |       |                   |       |                  |
+-----------+       |  INSERT/UPDATE    |       |  Journey Engine  |
                    |  on any table     |       |  State Machine   |
                    |       |           |       |  Action Dispatch |
                    |       v           |       |       |          |
                    |  skene_growth     |       |       v          |
                    |  .event_log       | ----> |  Email, Webhook  |
                    |  (pg_net webhook) |       |  Analytics, etc  |
                    +-------------------+       +------------------+
```

**1. Connect your Supabase project** to Skene Cloud. The engine introspects your schema and discovers all Skene DB tables, columns, foreign keys, and enums automatically.

**2. The AI compiler maps your schema to lifecycles.** It reads your enums (`deal_status`, `ticket_status`, `contact_type`, `subscription_status`) and generates lifecycle definitions with stages, transitions, and conditions. No manual configuration.

**3. Deploy triggers with one click.** Skene Cloud generates PL/pgSQL trigger functions on your Skene DB tables and deploys them to your Supabase project. When a row changes, the trigger writes to `skene_growth.event_log`, which forwards to Skene Cloud via `pg_net`.

**4. The journey engine processes events in real-time.** Every INSERT, UPDATE, or DELETE on your tables can trigger automated actions: emails, webhooks, analytics events, state transitions. Deterministic condition gates with an optional AI semantic layer for edge cases.

### What you get

#### Customer journey automation
Build journeys across your entire schema. A contact moves from lead to prospect to customer. A deal moves through pipeline stages. A ticket escalates through SLA tiers. Skene Cloud tracks every entity's journey and triggers actions at each transition.

#### Pipeline lifecycle builder
The same journey builder that tracks product onboarding works for sales pipelines, support queues, hiring funnels, and subscription lifecycles. Every Skene DB enum is a lifecycle waiting to be visualized and automated.

| Lifecycle | Source | Stages |
|-----------|--------|--------|
| Contact | `contact_type` enum | lead > prospect > customer > partner |
| Deal | `pipeline_stages` table | Lead > Qualified > Proposal > Negotiation > Closed Won |
| Ticket | `ticket_status` enum | open > pending > resolved > closed |
| Task | `task_status` enum | todo > in_progress > in_review > done |
| Subscription | `subscription_status` enum | trialing > active > past_due > canceled |
| Invoice | `invoice_status` enum | draft > open > paid > void |
| Document | `document_status` enum | draft > published > archived |

#### Cross-entity orchestration
The real power is connecting lifecycles across entities:

- **Lead-to-Revenue**: Contact created > first deal > deal won > subscription created > first payment
- **Support-driven retention**: Ticket spike > subscription at risk > proactive outreach > saved or churned
- **Product-led growth**: User signup > feature adoption > team invite > upgrade > expansion deal

#### Built-in actions
When a lifecycle transition fires, Skene Cloud can:

- Send emails via Resend (AI-generated or template-based)
- POST to any webhook with variable interpolation
- Fire analytics events for your data warehouse
- Create follow-up tasks or tickets in your Skene DB
- Trigger custom actions via the tool registry

### When you're ready

```bash
# 1. You already have the schema
supabase db push

# 2. Sign up at skene.ai and connect your Supabase project
#    The engine introspects your schema automatically

# 3. The AI compiler generates lifecycles and suggests automations
#    Activate the ones you want. Triggers deploy to your database.
```

Your schema stays in your database. Skene Cloud reads events, processes journeys, and dispatches actions. Disconnect at any time and keep everything. The schema has zero dependencies on Skene Cloud.

---

## Adding the schema to Supabase

### Option A: New project

```bash
# Create a new Supabase project at supabase.com, then:
git clone https://github.com/skene-ai/skene-db.git
cd skene-db
supabase link --project-ref <your-project-ref>
supabase db push
```

### Option B: Existing project

Skene DB migrations are designed to be additive. They create new tables and enums in the `public` schema without touching existing tables.

```bash
# Copy the migrations into your existing Supabase project
cp skene-db/supabase/migrations/* your-project/supabase/migrations/

# Push to your project
cd your-project
supabase db push
```

If you have existing tables with the same names (unlikely unless you've already built a CRM/helpdesk), review the migrations first and rename as needed.

### Option C: Local development

```bash
git clone https://github.com/skene-ai/skene-db.git
cd skene-db
supabase start
supabase db reset

# Load demo data
psql "postgresql://postgres:postgres@127.0.0.1:54322/postgres" -f seed/demo.sql

# Open Studio at http://localhost:54323
```

### Verify the schema

After pushing, open Supabase Studio (or connect via `psql`) and run:

```sql
-- Count all Skene DB tables
SELECT count(*) FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE';
-- Expected: 37

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

Skene DB's `users` table links to Supabase Auth via `auth_id`. Add this trigger to auto-create a user row on signup:

```sql
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger AS $$
BEGIN
  INSERT INTO public.users (auth_id, email, full_name, org_id)
  VALUES (
    NEW.id,
    NEW.email,
    coalesce(NEW.raw_user_meta_data->>'full_name', NEW.email),
    -- Set org_id based on your onboarding flow
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

| | Salesforce/HubSpot | Skene DB |
|---|---|---|
| **Data ownership** | Their servers, their rules, their API limits | Your Supabase project, your Postgres, your data |
| **AI/ML access** | Restricted. Many vendors prohibit using your data with third-party AI | Full access. Train models, build features, pipe into any tool |
| **Pricing** | Per-seat. $25-300/user/month | Supabase pricing. $25/month for most projects |
| **Customization** | Point-and-click config, proprietary scripting | Raw SQL. Extend with Edge Functions, Realtime, Storage |
| **Vendor lock-in** | Years of migration work to leave | `pg_dump` and you're done |
| **Schema access** | Abstracted behind proprietary ORM | Direct Postgres. Every tool in the ecosystem works |
| **Open source** | No | Yes. MIT licensed. Fork it, modify it, ship it |

---

## FAQ

**Why not EAV (Entity-Attribute-Value)?**
Real typed tables for the 80% case. JSONB `metadata` column plus `custom_field_definitions` / `custom_field_values` for the 20%. You get query performance and type safety where it matters, flexibility where you need it.

**Can I delete tables I don't need?**
Yes. Every module is self-contained except the Identity layer. See [docs/modules.md](docs/modules.md) for the dependency graph.

**What about the UI?**
Skene DB is the backend. Pair with any frontend framework, admin panel builder, or let an AI coding agent build the UI from this schema. The tables are designed to be straightforward to query from any client.

**Does this work without Skene Cloud?**
Yes, 100% standalone. No dependencies on Skene services. Skene Cloud adds automation and journey tracking, but Skene DB is a complete backend on its own.

**Can I use this with an AI coding agent?**
That's the ideal workflow. Give your AI agent this schema and it has everything it needs: typed tables, clear relationships, sensible enums, and example queries in [docs/examples.md](docs/examples.md).

---

## Contributing

PRs welcome. If you are adding a new module, follow the existing patterns:

- Base columns on every table (`id`, `org_id`, `created_at`, `updated_at`, `metadata`)
- Postgres enums for status/type fields
- `COMMENT ON` for tables and non-obvious columns
- Indexes on `org_id` and frequently filtered columns
- RLS policies in `00013_rls_policies.sql`
- Update the seed data and docs

---

## License

MIT

---

<p align="center">
  Built by <a href="https://skene.ai">Skene</a>
</p>
