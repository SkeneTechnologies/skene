# Modules

Skene DB is organized into 12 modules. Each module is a self-contained migration file, except that every module depends on the **Identity** module (migration `00001`).

## Module dependency graph

```
Identity (00001) ─── required by everything
├── CRM (00002)
├── Pipeline (00003) ─── depends on CRM (contacts, companies)
├── Tasks (00004)
├── Support (00005) ─── depends on CRM (contacts)
├── Comms (00006) ─── depends on CRM (contacts), Support (channel_type enum)
├── Content (00007)
├── Billing (00008) ─── depends on CRM (contacts, companies)
├── Calendar (00009) ─── depends on CRM (contacts)
├── Automations (00010)
├── Flexible Data (00011)
├── Activity (00012)
└── RLS Policies (00013) ─── depends on all of the above
```

## Dropping modules you don't need

Every module except Identity is optional. To remove a module:

1. Delete its migration file
2. Delete its RLS policies from `00013_rls_policies.sql`
3. Check the dependency graph above and remove any modules that depend on it
4. Update the seed file if needed

### Safe to drop independently

These modules have no downstream dependents:

- **Tasks** (00004) - projects, tasks, task_dependencies
- **Content** (00007) - folders, documents, comments
- **Automations** (00010) - automations, automation_actions, automation_runs
- **Flexible Data** (00011) - tags, taggings, custom_field_definitions, custom_field_values
- **Activity** (00012) - activities

### Require care when dropping

- **CRM** (00002) - Pipeline, Support, Comms, Billing, and Calendar reference contacts/companies. Drop CRM and you need to drop those too, or remove the foreign key columns.
- **Pipeline** (00003) - No other module references it directly, but the seed data and activity log reference deals.
- **Support** (00005) - Comms reuses the `channel_type` enum defined here. If dropping Support but keeping Comms, move the enum definition to Comms.
- **Billing** (00008) - Activity log references subscriptions and invoices. Update the CHECK constraint on activities if dropping.
- **Calendar** (00009) - Flexible Data's taggings CHECK constraint includes 'event'. Update if dropping.

## Module details

### Identity (00001)

The foundation. Defines the `set_updated_at()` trigger function, RLS helper functions, and the core identity tables.

| Table | Purpose |
|-------|---------|
| organizations | Root tenant. Every other table references this via org_id. |
| users | Application users. Linked to Supabase Auth via auth_id. |
| teams | Named groups of users (Sales, Engineering, etc). |
| memberships | Joins users to orgs with a role. Source of truth for access. |
| roles | Named permission sets for granular access control. |
| permissions | Individual resource + action pairs assigned to roles. |

### CRM (00002)

People and companies you do business with.

| Table | Purpose |
|-------|---------|
| contacts | External people (leads, prospects, customers). |
| companies | External organizations your contacts work at. |
| contact_companies | Many-to-many link between contacts and companies. |

### Pipeline (00003)

Deal tracking through configurable stages.

| Table | Purpose |
|-------|---------|
| pipelines | Named workflows with ordered stages (Sales, Recruiting). |
| pipeline_stages | Ordered stages within a pipeline. |
| deals | Opportunities moving through a pipeline with value and status. |
| deal_stage_history | Immutable log of every stage transition. |

### Tasks (00004)

Project and task management.

| Table | Purpose |
|-------|---------|
| projects | Containers for related tasks with their own status and timeline. |
| tasks | Individual work items assigned to users. |
| task_dependencies | Defines blocking relationships between tasks. |

### Support (00005)

Customer support tickets.

| Table | Purpose |
|-------|---------|
| tickets | Support requests with status, priority, channel, and SLA tracking. |

### Comms (00006)

Conversations attached to any entity.

| Table | Purpose |
|-------|---------|
| threads | Conversation threads linked to entities via polymorphic reference. |
| messages | Individual messages within threads (inbound, outbound, internal). |

### Content (00007)

Documents, folders, and comments.

| Table | Purpose |
|-------|---------|
| folders | Hierarchical folder structure with self-referencing parent. |
| documents | Content items (wiki pages, notes) within folders. |
| comments | Polymorphic comments on any entity. Supports threaded replies. |

### Billing (00008)

Products, pricing, subscriptions, and payments. Stripe-ready.

| Table | Purpose |
|-------|---------|
| products | Things you sell. Optional Stripe product sync. |
| prices | Pricing options (monthly, annual, one-time) for products. |
| subscriptions | Active subscriptions linking contacts/companies to prices. |
| invoices | Billing documents generated from subscriptions or manually. |
| payments | Individual payment transactions against invoices. |

### Calendar (00009)

Events and scheduling.

| Table | Purpose |
|-------|---------|
| events | Calendar events with optional polymorphic entity link. |
| event_attendees | Event participants (users or contacts). |

### Automations (00010)

Workflow automation definitions and execution logs.

| Table | Purpose |
|-------|---------|
| automations | Automation definitions with trigger type and config. |
| automation_actions | Ordered steps within an automation. |
| automation_runs | Execution log with status and results. |

### Flexible Data (00011)

Tags and custom fields for extensibility.

| Table | Purpose |
|-------|---------|
| tags | Org-scoped labels. |
| taggings | Polymorphic join table applying tags to any entity. |
| custom_field_definitions | Defines custom fields scoped to entity types. |
| custom_field_values | Stores typed values for custom fields on entity instances. |

### Activity (00012)

Audit trail for everything.

| Table | Purpose |
|-------|---------|
| activities | Polymorphic audit log recording every significant action. |

### RLS Policies (00013)

Row Level Security for every table. Not a module per se, but a migration that locks down the entire schema.

- Base pattern: org isolation via `get_user_org_id()`
- Delete restricted to admin/owner via `is_admin()`
- Special cases for organizations, users, and memberships
