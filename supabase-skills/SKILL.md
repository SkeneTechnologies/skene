---
name: supabase-skills
description: Ready-made Supabase schemas for business apps
---

# Supabase Skills

A collection of composable, independently installable backend schemas for Supabase. Each skill adds a set of tables, enums, RLS policies, and seed data to your project.

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
