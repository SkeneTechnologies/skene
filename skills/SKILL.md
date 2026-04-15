---
name: "@skene/database-skills"
description: Backend skills for Supabase
---

# Skene Skills

A collection of composable, independently installable backend schemas for Supabase. Each skill adds a set of tables, enums, RLS policies, and seed data to your project.

## Available Skills

| Skill | Tables | Description |
|-------|--------|-------------|
| [identity](identity/SKILL.md) | 6 | Organizations, users, teams, memberships, roles, permissions |
| [crm](crm/SKILL.md) | 3 | Contacts, companies, and relationships |
| [pipeline](pipeline/SKILL.md) | 4 | Pipelines, stages, deals, and stage history |
| [tasks](tasks/SKILL.md) | 3 | Projects, tasks, and dependencies |
| [support](support/SKILL.md) | 1 | Tickets with priority, status, and channel tracking |
| [comms](comms/SKILL.md) | 2 | Threads and messages for any entity |
| [content](content/SKILL.md) | 3 | Folders, documents, and comments |
| [billing](billing/SKILL.md) | 5 | Products, prices, subscriptions, invoices, payments |
| [calendar](calendar/SKILL.md) | 2 | Events and attendees |
| [automations](automations/SKILL.md) | 3 | Triggers, actions, and execution logs |
| [analytics](analytics/SKILL.md) | 5 | Tags, custom fields, and activity log |
| [forms](forms/SKILL.md) | 4 | Form definitions, fields, submissions, file uploads |
| [notifications](notifications/SKILL.md) | 4 | Templates, delivery log, preferences, push tokens |
| [campaigns](campaigns/SKILL.md) | 5 | Campaigns, segments, lists, sends, engagement events |
| [commerce](commerce/SKILL.md) | 6 | Orders, carts, shipping, fulfillments |
| [knowledge](knowledge/SKILL.md) | 3 | Articles, categories, publish status |
| [approvals](approvals/SKILL.md) | 5 | Approval chains, requests, decisions, delegations |
| [integrations](integrations/SKILL.md) | 5 | Connected apps, OAuth tokens, webhooks, sync logs |
| [compliance](compliance/SKILL.md) | 3 | Consent records, deletion requests, retention policies |

## Installation

```bash
# Install a single skill (resolves dependencies automatically)
./scripts/install.sh crm

# Install everything
./scripts/install.sh all
```

Each skill includes:
- `migration.sql` -- schema (tables, enums, indexes, RLS policies)
- `seed.sql` -- demo data for development
- `manifest.json` -- metadata and dependency declarations
- `SKILL.md` -- documentation with example queries

## License

MIT
