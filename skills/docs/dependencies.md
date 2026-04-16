# Dependency Tree

Every skill depends on `identity` for multi-tenant RLS functions and the `organizations`/`users` tables. Some skills have additional dependencies.

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

## Dependency Table

| Skill | Depends On |
|-------|-----------|
| identity | (none) |
| crm | identity |
| pipeline | crm |
| tasks | identity |
| support | crm |
| comms | crm |
| content | identity |
| billing | crm |
| calendar | identity |
| automations | identity |
| analytics | identity |
| forms | identity |
| notifications | identity |
| campaigns | crm |
| commerce | billing |
| knowledge | content |
| approvals | identity |
| integrations | identity |
| compliance | identity |

## Install Order

The `install.sh` script resolves dependencies automatically via topological sort. If you install manually, follow this order:

1. identity
2. crm, tasks, content, calendar, automations, analytics, forms, notifications, approvals, integrations, compliance
3. pipeline, support, comms, billing, campaigns, knowledge
4. commerce

Skills at the same level can be installed in any order.

## Shared Enums

The `channel_type` enum is defined by both `support` and `comms`. Each skill uses a `CREATE TYPE IF NOT EXISTS` guard so either can be installed first, or both can coexist.
