---
name: support
description: Support tickets with priority, status, and SLA tracking
---

# Support

Support tickets linked to contacts, with priority levels, status tracking, and SLA metrics.

## Tables

### tickets

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated |
| org_id | uuid | References organizations. CASCADE on delete |
| contact_id | uuid | References contacts. SET NULL on delete |
| assignee_id | uuid | References users. SET NULL on delete |
| creator_id | uuid | References users. SET NULL on delete |
| title | text | Ticket title (required) |
| description | text | Optional ticket description |
| status | ticket_status | Current status, defaults to 'open' |
| priority | ticket_priority | Priority level, defaults to 'medium' |
| channel | channel_type | How the ticket was created (email, sms, etc.) |
| resolved_at | timestamptz | When the ticket was resolved |
| closed_at | timestamptz | When the ticket was closed |
| first_response_at | timestamptz | For SLA tracking |
| created_at | timestamptz | Row creation time |
| updated_at | timestamptz | Auto-updated on change via trigger |
| metadata | jsonb | Freeform JSON, defaults to empty object |

## Enums

### ticket_status

| Value | Description |
|-------|-------------|
| open | New or reopened, needs attention |
| pending | Waiting on customer or third party |
| resolved | Solution provided |
| closed | Ticket closed, no further action |

### ticket_priority

| Value | Description |
|-------|-------------|
| low | Low priority |
| medium | Medium priority (default) |
| high | High priority |
| urgent | Needs immediate attention |

### channel_type

| Value | Description |
|-------|-------------|
| email | Email channel |
| sms | SMS / text message |
| chat | Live chat or messaging |
| phone | Phone call |
| social | Social media |

## Row-Level Security

RLS is enabled and scoped to org_id via `get_user_org_id()`. SELECT, INSERT, and UPDATE are open to all org members. DELETE requires admin privileges via `is_admin()`.

## Dependencies

- identity (organizations, users)

## Example Queries

```sql
-- Open tickets sorted by priority and age
SELECT
  t.title,
  t.priority,
  t.channel,
  c.first_name || ' ' || coalesce(c.last_name, '') AS contact,
  u.full_name AS assignee,
  extract(epoch FROM now() - t.created_at) / 3600 AS hours_open
FROM tickets t
LEFT JOIN contacts c ON c.id = t.contact_id
LEFT JOIN users u ON u.id = t.assignee_id
WHERE t.status IN ('open', 'pending')
ORDER BY
  CASE t.priority
    WHEN 'urgent' THEN 0
    WHEN 'high' THEN 1
    WHEN 'medium' THEN 2
    WHEN 'low' THEN 3
  END,
  t.created_at ASC;
```

```sql
-- Average first response time by priority (last 30 days)
SELECT
  t.priority,
  count(*) AS ticket_count,
  round(
    avg(extract(epoch FROM t.first_response_at - t.created_at)) / 3600, 1
  ) AS avg_response_hours
FROM tickets t
WHERE t.first_response_at IS NOT NULL
  AND t.created_at >= now() - interval '30 days'
GROUP BY t.priority
ORDER BY
  CASE t.priority
    WHEN 'urgent' THEN 0
    WHEN 'high' THEN 1
    WHEN 'medium' THEN 2
    WHEN 'low' THEN 3
  END;
```

```sql
-- Ticket volume by channel and status
SELECT
  t.channel,
  count(*) FILTER (WHERE t.status = 'open') AS open,
  count(*) FILTER (WHERE t.status = 'pending') AS pending,
  count(*) FILTER (WHERE t.status = 'resolved') AS resolved,
  count(*) FILTER (WHERE t.status = 'closed') AS closed,
  count(*) AS total
FROM tickets t
GROUP BY t.channel
ORDER BY total DESC;
```

```sql
-- Unassigned tickets ordered by priority
SELECT
  t.title,
  t.priority,
  t.channel,
  t.created_at,
  c.first_name || ' ' || coalesce(c.last_name, '') AS contact
FROM tickets t
LEFT JOIN contacts c ON c.id = t.contact_id
WHERE t.assignee_id IS NULL
  AND t.status IN ('open', 'pending')
ORDER BY
  CASE t.priority
    WHEN 'urgent' THEN 0
    WHEN 'high' THEN 1
    WHEN 'medium' THEN 2
    WHEN 'low' THEN 3
  END,
  t.created_at ASC;
```

```sql
-- Average resolution time by assignee (last 30 days)
SELECT
  u.full_name,
  count(*) AS resolved_count,
  round(
    avg(extract(epoch FROM t.resolved_at - t.created_at)) / 3600, 1
  ) AS avg_resolution_hours
FROM tickets t
JOIN users u ON u.id = t.assignee_id
WHERE t.resolved_at IS NOT NULL
  AND t.resolved_at >= now() - interval '30 days'
GROUP BY u.id, u.full_name
ORDER BY avg_resolution_hours ASC;
```
