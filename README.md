<p align="center">
  <img width="4000" height="800" alt="Skene_git" src="https://github.com/user-attachments/assets/2be11c04-6b98-4e26-8905-bf3250c4addb" />
</p>

<h3 align="center">Backend skills for your Supabase</h3>

<p align="center">
  <a href="https://www.skene.ai"><img width="120" height="42" alt="website" src="https://github.com/user-attachments/assets/8ae8c68f-eeb5-411f-832f-6b6818bd2c34"></a>
  <a href="https://www.skene.ai/resources/docs/skene"><img width="120" height="42" alt="docs" src="https://github.com/user-attachments/assets/f847af52-0f6f-4570-9a48-1b7c8f4f0d7a"></a>
  <a href="https://www.skene.ai/resources/blog"><img width="100" height="42" alt="blog" src="https://github.com/user-attachments/assets/8c62e3b8-39a8-43f6-bb0b-f00b118aff82"></a>
  <a href="https://www.reddit.com/r/plgbuilders/"><img width="153" height="42" alt="reddit" src="https://github.com/user-attachments/assets/b420ea50-26e3-40fe-ab34-ac179f748357"></a>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License" /></a>
  <a href="https://supabase.com"><img src="https://img.shields.io/badge/Supabase-ready-3ECF8E?logo=supabase&logoColor=white" alt="Supabase Ready" /></a>
  <a href="https://skills.sh"><img src="https://img.shields.io/badge/skills.sh-compatible-000000" alt="skills.sh" /></a>
</p>

---

Install backend Skills into your Supabase project. CRM, billing, helpdesk, project management, calendar, and more. Each Skill adds tables, enums, RLS policies, and seed data. Pick what you need.

```bash
npx skills add SkeneTechnologies/skene
```

The same data model that powers Salesforce, HubSpot, Jira, Zendesk, and Stripe. Except you own it.

---

## Quick Start

```bash
# Install all skills
npx skills add SkeneTechnologies/skene

# Or pick specific ones
npx skills add SkeneTechnologies/skene -s crm
npx skills add SkeneTechnologies/skene -s billing
```

Skills install to `.claude/skills/`. Your AI agent reads the SKILL.md files, understands the schema, and applies the migrations to your Supabase project.

Or apply SQL directly -- no agent needed:

```bash
psql "$DATABASE_URL" -f identity/migration.sql
psql "$DATABASE_URL" -f crm/migration.sql
```

## Available Skills

| Skill | What it adds | Depends on |
|-------|-------------|------------|
| `identity` | Organizations, users, teams, roles, permissions | -- |
| `crm` | Contacts, companies, relationships | identity |
| `pipeline` | Deals, stages, stage history | crm |
| `tasks` | Projects, tasks, dependencies | identity |
| `support` | Tickets with priorities, SLAs, channels | crm |
| `comms` | Threads and messages for any entity | crm |
| `content` | Folders, documents, comments | identity |
| `billing` | Products, prices, subscriptions, invoices, payments | crm |
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

## What You Can Build

```
CRM            = identity + crm + pipeline + comms + analytics
Project tool   = identity + tasks + content + analytics
Helpdesk       = identity + crm + support + comms + knowledge + analytics
Billing app    = identity + crm + billing + commerce + analytics
Marketing      = identity + crm + campaigns + forms + analytics
Internal wiki  = identity + content + knowledge
Full business  = install all 19 skills
```

## Why This Exists

AI can build a frontend in minutes. Cursor, Claude Code, v0, Bolt -- they generate UI fast. But every project still starts with an empty Postgres instance and a blank migration file.

Every founder using AI to build a SaaS product hits the same wall in the first hour. What tables do I need? How do I handle multi-tenancy? What should my RLS look like?

These are solved problems. Skene Skills are the starting line so you skip them.

## Monorepo

| Directory | What | Distribution |
|-----------|------|-------------|
| [`skills/`](skills/) | Composable backend schemas for Supabase | [`npx skills add`](https://skills.sh) |
| `src/skene/` | PLG analysis CLI | [PyPI](https://pypi.org/project/skene/) |
| `tui/` | Interactive terminal UI | [GitHub Releases](https://github.com/SkeneTechnologies/skene/releases) |
| `cursor-plugin/` | Cursor IDE plugin | -- |

See [`skills/README.md`](skills/README.md) for full documentation -- schema design principles, AI agent integration, Skene Cloud, and more.

## Contributing

Contributions welcome. Please [open an issue](https://github.com/SkeneTechnologies/skene/issues) or submit a [pull request](https://github.com/SkeneTechnologies/skene/pulls). See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup.

## License

[MIT](https://opensource.org/licenses/MIT)

<img width="4000" height="800" alt="Skene_end_git" src="https://github.com/user-attachments/assets/04119cd1-ee00-4902-9075-5fc3e1e5ec48" />
