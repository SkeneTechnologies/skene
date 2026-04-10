# Demo Walkthrough

This guide walks through the full flow: adding the Skene DB schema to your Supabase project, verifying it works, and optionally connecting Skene Cloud for automated journeys.

---

## Step 1: Push the schema

```bash
git clone https://github.com/skene-ai/skene-db.git
cd skene-db
supabase link --project-ref <your-project-ref>
supabase db push
```

After pushing, your Supabase project has 37 tables, 22 enums, indexes, triggers, and RLS policies. Open Supabase Studio to verify:

```
+-------------------------------------------------------+
|  Supabase Studio > Table Editor                        |
|                                                        |
|  Tables (37)                                           |
|                                                        |
|  > organizations          > pipelines                  |
|  > users                  > pipeline_stages            |
|  > teams                  > deals                      |
|  > memberships            > deal_stage_history         |
|  > roles                  > projects                   |
|  > permissions            > tasks                      |
|  > contacts               > task_dependencies          |
|  > companies              > tickets                    |
|  > contact_companies      > threads                    |
|  > products               > messages                   |
|  > prices                 > folders                    |
|  > subscriptions          > documents                  |
|  > invoices               > comments                   |
|  > payments               > events                     |
|  > automations            > event_attendees            |
|  > automation_actions     > tags                       |
|  > automation_runs        > taggings                   |
|  > activities             > custom_field_definitions   |
|                           > custom_field_values        |
+-------------------------------------------------------+
```

## Step 2: Load demo data (optional)

```bash
psql "$DATABASE_URL" -f seed/demo.sql
```

This creates Acme Corp with 5 users, 20 contacts, 8 companies, 5 deals across 2 pipelines, 10 tasks, 5 tickets, 15 messages, billing data, and 30+ activity records. Useful for testing queries and seeing how the schema feels with real data.

At this point, you have a fully working backend. Build your UI, query with any Supabase client, extend with Edge Functions. The schema is yours to use however you want.

---

## Optional: Connect Skene Cloud

The steps below show what happens when you connect your Skene DB project to [Skene Cloud](https://skene.ai). This is not required. Skene Cloud adds automated journeys and lifecycle tracking on top of your existing schema.

## Step 3: Connect to Skene Cloud

Sign up at [skene.ai](https://skene.ai) and create a workspace.

### 3a. Integrations page

Navigate to **Integrations** and connect your Supabase project.

```
+-------------------------------------------------------+
|  Integrations                                          |
|  Connected services and database configuration         |
|                                                        |
|  +---------------------------------------------------+|
|  |  [S] Supabase              [checkmark] Connected  ||
|  |  PostgreSQL database connection                    ||
|  |                                                    ||
|  |  Project ID:    abcdefghijklmnop                   ||
|  |  Cloud Endpoint: Default (skene.ai)                ||
|  |  Connection:     ••••••••••••••••                   ||
|  |  PAT:            ••••••••••••••••                   ||
|  +---------------------------------------------------+|
|                                                        |
|  Skene Growth Schema                                   |
|  +---------------------------------------------------+|
|  |  [ok]  skene_growth schema                         ||
|  |  [ok]    event_log                                 ||
|  |  [ok]    failed_events                             ||
|  |  [ok]    enrichment_map                            ||
|  |  [ok]  enrich_event() function                     ||
|  |  [ok]  event_log webhook                           ||
|  +---------------------------------------------------+|
+-------------------------------------------------------+
```

When you connect, Skene Cloud:
1. Creates the `skene_growth` schema in your database (event_log, failed_events, enrichment_map)
2. Sets up the event enrichment trigger
3. Configures the pg_net webhook to forward events to Skene Cloud

## Step 4: Schema analysis

Navigate to **AI Model**. The engine introspects your Skene DB schema.

```
+-------------------------------------------------------+
|  AI Model                                              |
|  Schema analysis and lifecycle compilation             |
|                                                        |
|  Analysis Progress:                                    |
|  [====] Analyzing Schema                               |
|         Introspecting Supabase tables...               |
|                                                        |
|  Discovered Tables:                                    |
|  +---------------------------------------------------+|
|  |  public.contacts       | 19 cols | 3 FKs | enums ||
|  |  public.deals          | 17 cols | 6 FKs | enums ||
|  |  public.tickets        | 15 cols | 3 FKs | enums ||
|  |  public.subscriptions  | 17 cols | 3 FKs | enums ||
|  |  public.tasks          | 14 cols | 3 FKs | enums ||
|  |  public.users          | 12 cols | 1 FK  |       ||
|  |  ... 31 more tables                               ||
|  +---------------------------------------------------+|
+-------------------------------------------------------+
```

The AI compiler reads your enums and generates lifecycle definitions:

```
+-------------------------------------------------------+
|  Compiled Lifecycles                                   |
|                                                        |
|  Contact Lifecycle (from contact_type enum)            |
|  [lead] ---> [prospect] ---> [customer] ---> [partner]|
|   blue        blue            green           green    |
|                                                        |
|  Deal Lifecycle (from pipeline_stages + deal_status)   |
|  [Lead] -> [Qualified] -> [Proposal] -> [Won/Lost]    |
|   gray      blue           amber        green/red     |
|                                                        |
|  Ticket Lifecycle (from ticket_status enum)            |
|  [open] ---> [pending] ---> [resolved] ---> [closed]  |
|   red         amber          green           gray      |
|                                                        |
|  Subscription Lifecycle (from subscription_status)     |
|  [trialing] -> [active] -> [past_due] -> [canceled]   |
|   blue          green       amber          red         |
|                                                        |
|  Task Lifecycle (from task_status enum)                |
|  [todo] -> [in_progress] -> [in_review] -> [done]     |
|   gray      blue             amber          green      |
+-------------------------------------------------------+
```

## Step 5: Journey builder

The journey builder visualizes entity lifecycles as interactive state machine graphs. Each node is a lifecycle stage. Each edge is a transition. Growth loops attach to transitions.

```
+-------------------------------------------------------+
|  Journey Builder: Deal Lifecycle                       |
|                                                        |
|    [Lead]                                              |
|      |                                                 |
|      | --> welcome_email (on enter)                    |
|      v                                                 |
|    [Qualified]                                         |
|      |                                                 |
|      | --> create_followup_task (on enter)             |
|      v                                                 |
|    [Proposal]                                          |
|      |                                                 |
|      | --> stale_deal_alert (if no change in 14d)      |
|      v                                                 |
|    [Negotiation]                                       |
|      |                                                 |
|      +--> [Closed Won] --> celebration_email           |
|      |                 --> create_invoice               |
|      |                 --> update_contact_type          |
|      |                                                 |
|      +--> [Lost] --> lost_reason_survey                |
|                  --> schedule_reengagement_90d          |
+-------------------------------------------------------+
```

This is the same interactive ReactFlow graph the dashboard uses for product feature lifecycles, extended to work with any Skene DB entity.

## Step 6: Configure growth loops

Navigate to **Actions** to see detected growth features and configure loops.

```
+-------------------------------------------------------+
|  Growth Features                                       |
|  12 growth features detected from your schema          |
|                                                        |
|  [My features]  Library                                |
|                                                        |
|  +---------------------------------------------------+|
|  | [zap] Welcome Email                     [active]  ||
|  |       Send welcome email on user signup            ||
|  |       Trigger: INSERT on public.users              ||
|  +---------------------------------------------------+|
|  | [zap] Deal Stage Alert                  [active]  ||
|  |       Notify owner when deal changes stage         ||
|  |       Trigger: UPDATE on public.deals              ||
|  +---------------------------------------------------+|
|  | [zap] Ticket SLA Escalation             [active]  ||
|  |       Escalate if no response in 4 hours           ||
|  |       Trigger: SCHEDULED on public.tickets         ||
|  +---------------------------------------------------+|
|  | [zap] Payment Received                  [active]  ||
|  |       Track revenue event on payment               ||
|  |       Trigger: INSERT on public.payments           ||
|  +---------------------------------------------------+|
|  | [zap] Stale Deal Alert                  [draft]   ||
|  |       Alert when deal stuck for 14 days            ||
|  |       Trigger: SCHEDULED on public.deals           ||
|  +---------------------------------------------------+|
|  | [zap] Subscription Churn Prevention     [draft]   ||
|  |       Email sequence when past_due                 ||
|  |       Trigger: UPDATE on public.subscriptions      ||
|  +---------------------------------------------------+|
|  | ... 6 more features                               ||
+-------------------------------------------------------+
```

## Step 7: Deploy triggers

When you activate a loop, Skene Cloud deploys a PL/pgSQL trigger to your Supabase database. One trigger per unique (table, operation) combination.

```
+-------------------------------------------------------+
|  Triggers                                              |
|  6 triggers deployed to your Supabase project          |
|                                                        |
|  +---------------------------------------------------+|
|  | skene_growth_trg_users_insert          [deployed]  ||
|  |   public.users > AFTER INSERT                      ||
|  |   Loops: welcome_email                             ||
|  +---------------------------------------------------+|
|  | skene_growth_trg_deals_update          [deployed]  ||
|  |   public.deals > AFTER UPDATE                      ||
|  |   Loops: deal_stage_alert, stale_deal_check        ||
|  +---------------------------------------------------+|
|  | skene_growth_trg_tickets_insert        [deployed]  ||
|  |   public.tickets > AFTER INSERT                    ||
|  |   Loops: ticket_sla_escalation                     ||
|  +---------------------------------------------------+|
|  | skene_growth_trg_payments_insert       [deployed]  ||
|  |   public.payments > AFTER INSERT                   ||
|  |   Loops: payment_received                          ||
|  +---------------------------------------------------+|
|  | skene_growth_trg_subscriptions_update  [deployed]  ||
|  |   public.subscriptions > AFTER UPDATE              ||
|  |   Loops: churn_prevention                          ||
|  +---------------------------------------------------+|
|  | skene_growth_trg_contacts_insert       [deployed]  ||
|  |   public.contacts > AFTER INSERT                   ||
|  |   Loops: new_lead_welcome                          ||
|  +---------------------------------------------------+|
+-------------------------------------------------------+
```

## Step 8: Watch it work

Navigate to **Logs** to see events flowing in real-time.

```
+-------------------------------------------------------+
|  Trigger Logs                                          |
|                                                        |
|  +---------------------------------------------------+|
|  | 2 min ago  public.deals.update                     ||
|  |   Entity: a3000000-...-000000000001                ||
|  |   Loop: deal_stage_alert                           ||
|  |   Gate: PASS (conditions_met)                      ||
|  |   Action: email > sarah@acme.io                    ||
|  |   "Deal moved from Proposal to Negotiation"        ||
|  +---------------------------------------------------+|
|  | 5 min ago  public.contacts.insert                  ||
|  |   Entity: f2000000-...-000000000021                ||
|  |   Loop: new_lead_welcome                           ||
|  |   Gate: PASS (conditions_met)                      ||
|  |   Action: email > newlead@company.com              ||
|  |   "Welcome email sent"                             ||
|  +---------------------------------------------------+|
|  | 12 min ago  public.payments.insert                 ||
|  |   Entity: af000000-...-000000000002                ||
|  |   Loop: payment_received                           ||
|  |   Gate: PASS (conditions_met)                      ||
|  |   Action: analytics > payment_received             ||
|  |   "Revenue event tracked: $49,500"                 ||
|  +---------------------------------------------------+|
+-------------------------------------------------------+
```

## Step 9: Analytics

Navigate to **Analytics** to see loop performance.

```
+-------------------------------------------------------+
|  Analytics                                             |
|                                                        |
|  Total fires: 847    Active features: 8                |
|  Unique subjects: 312    Features with loops: 12       |
|                                                        |
|  +---------------------------------------------------+|
|  | Feature              | Fires | Subjects | Score   ||
|  |----------------------|-------|----------|---------|
|  | Welcome Email        |  234  |    234   |  0.92   ||
|  | Deal Stage Alert     |  156  |     42   |  0.88   ||
|  | Payment Received     |   89  |     67   |  0.95   ||
|  | Ticket SLA           |   78  |     45   |  0.71   ||
|  | Stale Deal Alert     |   34  |     28   |  0.84   ||
|  | Churn Prevention     |   12  |      8   |  0.67   ||
|  +---------------------------------------------------+|
+-------------------------------------------------------+
```

---

## The full picture

```
Your App (any frontend)
    |
    v
Skene DB (your Supabase)
    |
    |-- contacts, companies, deals, tickets, tasks, ...
    |-- enums define lifecycles (deal_status, ticket_status, ...)
    |-- activities table = built-in audit log
    |-- RLS enforces multi-tenant isolation
    |
    v
skene_growth.event_log (in your DB)
    |
    |-- Triggers fire on INSERT/UPDATE/DELETE
    |-- pg_net forwards to Skene Cloud
    |
    v
Skene Cloud (skene.ai)
    |
    |-- Schema discovery + AI compilation
    |-- Lifecycle definitions from your enums
    |-- Journey state tracking per entity
    |-- Deterministic gates + semantic matching
    |-- Action dispatch (email, webhook, analytics)
    |
    v
Your customers get onboarded, deals move forward,
tickets get resolved, subscriptions get saved.
```

The schema is yours. The automation is optional. Disconnect Skene Cloud and everything in your database still works. Reconnect and the engine picks up where it left off.
