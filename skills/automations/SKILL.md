---
name: automations
description: Trigger-based automations with action sequences and run history
---

# Automations

Trigger-based automations with ordered action sequences and execution history. Supports event, schedule, webhook, and manual triggers.

## Tables

### automations

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated |
| org_id | uuid | References organizations(id), cascade delete |
| creator_id | uuid | References users(id), set null on delete |
| name | text | Name of the automation |
| description | text | Optional description |
| trigger_type | automation_trigger_type | What starts this automation |
| trigger_config | jsonb | Cron expression, event filter, webhook URL, etc. |
| status | automation_status | Current lifecycle status, defaults to draft |
| last_run_at | timestamptz | Timestamp of the most recent run |
| run_count | integer | Total number of runs, defaults to 0 |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Auto-updated on modification |
| metadata | jsonb | Arbitrary key-value data |

### automation_actions

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated |
| org_id | uuid | References organizations(id), cascade delete |
| automation_id | uuid | References automations(id), cascade delete |
| action_type | text | Action kind: send_email, update_field, create_task, webhook, etc. |
| action_config | jsonb | Configuration for the action |
| position | integer | Execution order within the automation, defaults to 0 |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Auto-updated on modification |
| metadata | jsonb | Arbitrary key-value data |

### automation_runs

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated |
| org_id | uuid | References organizations(id), cascade delete |
| automation_id | uuid | References automations(id), cascade delete |
| status | run_status | Current run status, defaults to pending |
| started_at | timestamptz | When the run started executing |
| completed_at | timestamptz | When the run finished |
| error_message | text | Error details if the run failed |
| result | jsonb | Output data from the run |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Auto-updated on modification |
| metadata | jsonb | Arbitrary key-value data |

## Enums

### automation_trigger_type

| Value | Description |
|-------|-------------|
| event | Triggered by a system event |
| schedule | Triggered on a cron schedule |
| webhook | Triggered by an incoming webhook |
| manual | Triggered by a user action |

### automation_status

| Value | Description |
|-------|-------------|
| active | Running and ready to trigger |
| paused | Temporarily disabled |
| draft | Not yet activated |
| archived | Retired, no longer triggerable |

### run_status

| Value | Description |
|-------|-------------|
| pending | Queued but not yet started |
| running | Currently executing |
| completed | Finished successfully |
| failed | Finished with an error |

## Row-Level Security

All three tables are scoped to the current user's organization via `get_user_org_id()`. Select, insert, and update are allowed for any org member. Delete requires the `is_admin()` check.

## Dependencies

- identity -- organizations and users tables, `get_user_org_id()` and `is_admin()` functions, `set_updated_at()` trigger function

## Example Queries

List all active automations for the current org:

```sql
SELECT id, name, trigger_type, trigger_config, last_run_at, run_count
FROM automations
WHERE status = 'active'
ORDER BY created_at DESC;
```

Get the ordered action steps for a specific automation:

```sql
SELECT id, action_type, action_config, position
FROM automation_actions
WHERE automation_id = '<automation_id>'
ORDER BY position ASC;
```

Recent runs across all automations (last 50):

```sql
SELECT
  r.id,
  a.name AS automation_name,
  r.status,
  r.started_at,
  r.completed_at,
  r.error_message
FROM automation_runs r
JOIN automations a ON a.id = r.automation_id
ORDER BY r.started_at DESC
LIMIT 50;
```

Failed runs in the last 7 days:

```sql
SELECT
  r.id,
  a.name AS automation_name,
  r.error_message,
  r.started_at,
  r.result
FROM automation_runs r
JOIN automations a ON a.id = r.automation_id
WHERE r.status = 'failed'
  AND r.started_at >= now() - interval '7 days'
ORDER BY r.started_at DESC;
```

Automations with their action count:

```sql
SELECT
  a.id,
  a.name,
  a.status,
  a.trigger_type,
  count(aa.id) AS action_count
FROM automations a
LEFT JOIN automation_actions aa ON aa.automation_id = a.id
GROUP BY a.id, a.name, a.status, a.trigger_type
ORDER BY a.name;
```

Run success rate per automation:

```sql
SELECT
  a.name,
  a.run_count,
  count(r.id) FILTER (WHERE r.status = 'completed') AS succeeded,
  count(r.id) FILTER (WHERE r.status = 'failed') AS failed
FROM automations a
LEFT JOIN automation_runs r ON r.automation_id = a.id
GROUP BY a.id, a.name, a.run_count
ORDER BY a.name;
```
