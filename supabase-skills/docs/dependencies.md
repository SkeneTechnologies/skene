# Dependency Tree

Every skill depends on `identity` for multi-tenant RLS functions and the `organizations`/`users` tables. Some skills have additional dependencies.

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

## Dependency Table

| Skill | Depends On |
|-------|-----------|
| identity | (none) |
| crm | identity |
| pipeline | crm |
| tasks | identity |
| support | identity |
| comms | crm |
| content | identity |
| billing | crm |
| calendar | identity |
| automations | identity |
| analytics | identity |

## Install Order

The `install.sh` script resolves dependencies automatically via topological sort. If you install manually, follow this order:

1. identity
2. crm
3. pipeline, tasks, support, comms, content, billing, calendar, automations, analytics

Skills at the same level can be installed in any order.

## Shared Enums

The `channel_type` enum is defined by both `support` and `comms`. Each skill uses a `CREATE TYPE IF NOT EXISTS` guard so either can be installed first, or both can coexist.
