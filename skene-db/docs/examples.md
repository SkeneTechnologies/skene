# Example Queries

Real SQL queries showing common operations against the Skene DB schema. All queries assume you are operating within a single org context.

## CRM

### Get all contacts at a specific company

```sql
SELECT c.first_name, c.last_name, c.email, cc.title
FROM contacts c
JOIN contact_companies cc ON cc.contact_id = c.id
WHERE cc.company_id = '<company_id>'
  AND cc.is_primary = true
ORDER BY c.last_name;
```

### Search contacts by type with company info

```sql
SELECT
  c.first_name || ' ' || coalesce(c.last_name, '') AS name,
  c.email,
  c.type,
  co.name AS company
FROM contacts c
LEFT JOIN contact_companies cc ON cc.contact_id = c.id AND cc.is_primary = true
LEFT JOIN companies co ON co.id = cc.company_id
WHERE c.type = 'lead'
ORDER BY c.created_at DESC;
```

## Pipeline

### Get all deals in a specific stage

```sql
SELECT
  d.title,
  d.value / 100.0 AS value_dollars,
  d.currency,
  u.full_name AS owner,
  c.first_name || ' ' || coalesce(c.last_name, '') AS contact
FROM deals d
LEFT JOIN users u ON u.id = d.owner_id
LEFT JOIN contacts c ON c.id = d.contact_id
WHERE d.stage_id = '<stage_id>'
  AND d.status = 'open'
ORDER BY d.value DESC;
```

### Pipeline summary with deal counts and total value

```sql
SELECT
  ps.name AS stage,
  ps.position,
  count(d.id) AS deal_count,
  coalesce(sum(d.value), 0) / 100.0 AS total_value
FROM pipeline_stages ps
LEFT JOIN deals d ON d.stage_id = ps.id AND d.status = 'open'
WHERE ps.pipeline_id = '<pipeline_id>'
GROUP BY ps.id, ps.name, ps.position
ORDER BY ps.position;
```

### Average time in each stage (pipeline velocity)

```sql
SELECT
  ps.name AS stage,
  round(avg(dsh.duration_seconds) / 86400.0, 1) AS avg_days
FROM deal_stage_history dsh
JOIN pipeline_stages ps ON ps.id = dsh.from_stage_id
WHERE dsh.duration_seconds IS NOT NULL
GROUP BY ps.id, ps.name, ps.position
ORDER BY ps.position;
```

## Tasks

### Overdue tasks for a user

```sql
SELECT
  t.title,
  t.priority,
  t.due_at,
  p.name AS project
FROM tasks t
LEFT JOIN projects p ON p.id = t.project_id
WHERE t.assignee_id = '<user_id>'
  AND t.status NOT IN ('done', 'cancelled')
  AND t.due_at < current_date
ORDER BY t.due_at ASC;
```

### Project progress summary

```sql
SELECT
  p.name,
  count(*) FILTER (WHERE t.status = 'done') AS completed,
  count(*) FILTER (WHERE t.status NOT IN ('done', 'cancelled')) AS remaining,
  round(
    100.0 * count(*) FILTER (WHERE t.status = 'done') / nullif(count(*), 0),
    0
  ) AS percent_complete
FROM projects p
JOIN tasks t ON t.project_id = p.id
GROUP BY p.id, p.name;
```

## Support

### Open tickets sorted by priority and age

```sql
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

### Full ticket history with messages

```sql
SELECT
  t.title AS ticket_title,
  t.status,
  m.direction,
  coalesce(u.full_name, c.first_name || ' ' || coalesce(c.last_name, '')) AS sender,
  m.body,
  m.sent_at
FROM tickets t
JOIN threads th ON th.entity_type = 'ticket' AND th.entity_id = t.id
JOIN messages m ON m.thread_id = th.id
LEFT JOIN users u ON u.id = m.author_id
LEFT JOIN contacts c ON c.id = m.contact_id
WHERE t.id = '<ticket_id>'
ORDER BY m.sent_at ASC;
```

## Billing

### MRR calculation (Monthly Recurring Revenue)

```sql
SELECT
  sum(
    CASE p.interval
      WHEN 'month' THEN p.amount * s.quantity
      WHEN 'year'  THEN (p.amount * s.quantity) / 12
      ELSE 0
    END
  ) / 100.0 AS mrr_dollars
FROM subscriptions s
JOIN prices p ON p.id = s.price_id
WHERE s.status = 'active';
```

### Revenue by product

```sql
SELECT
  pr.name AS product,
  count(s.id) AS active_subscriptions,
  sum(s.quantity) AS total_seats,
  sum(
    CASE p.interval
      WHEN 'month' THEN p.amount * s.quantity * 12
      WHEN 'year'  THEN p.amount * s.quantity
      ELSE p.amount * s.quantity
    END
  ) / 100.0 AS arr_dollars
FROM products pr
JOIN prices p ON p.product_id = pr.id
JOIN subscriptions s ON s.price_id = p.id AND s.status = 'active'
GROUP BY pr.id, pr.name
ORDER BY arr_dollars DESC;
```

### Outstanding invoices

```sql
SELECT
  i.number,
  co.name AS company,
  i.total / 100.0 AS total_dollars,
  i.amount_due / 100.0 AS due_dollars,
  i.due_at,
  CASE
    WHEN i.due_at < now() THEN 'overdue'
    WHEN i.due_at < now() + interval '7 days' THEN 'due_soon'
    ELSE 'upcoming'
  END AS urgency
FROM invoices i
LEFT JOIN companies co ON co.id = i.company_id
WHERE i.status IN ('open', 'past_due')
ORDER BY i.due_at ASC;
```

## Activity

### Activity feed for a contact

```sql
SELECT
  a.action,
  a.description,
  a.entity_type,
  u.full_name AS actor,
  a.occurred_at
FROM activities a
LEFT JOIN users u ON u.id = a.actor_id
WHERE a.entity_type = 'contact' AND a.entity_id = '<contact_id>'
ORDER BY a.occurred_at DESC
LIMIT 50;
```

### Cross-entity activity feed (all activity for a deal and its related entities)

```sql
WITH deal_context AS (
  SELECT id AS entity_id, 'deal' AS entity_type FROM deals WHERE id = '<deal_id>'
  UNION ALL
  SELECT id, 'contact' FROM contacts WHERE id = (SELECT contact_id FROM deals WHERE id = '<deal_id>')
  UNION ALL
  SELECT id, 'company' FROM companies WHERE id = (SELECT company_id FROM deals WHERE id = '<deal_id>')
)
SELECT
  a.action,
  a.description,
  a.entity_type,
  u.full_name AS actor,
  a.changes,
  a.occurred_at
FROM activities a
JOIN deal_context dc ON a.entity_type = dc.entity_type AND a.entity_id = dc.entity_id
LEFT JOIN users u ON u.id = a.actor_id
ORDER BY a.occurred_at DESC
LIMIT 100;
```

## Flexible Data

### Get all tags for an entity

```sql
SELECT t.name, t.color
FROM tags t
JOIN taggings tg ON tg.tag_id = t.id
WHERE tg.entity_type = 'deal' AND tg.entity_id = '<deal_id>';
```

### Get custom field values for a contact

```sql
SELECT
  cfd.name AS field_name,
  cfd.field_type,
  coalesce(
    cfv.value_text,
    cfv.value_number::text,
    cfv.value_boolean::text,
    cfv.value_date::text,
    cfv.value_json::text
  ) AS value
FROM custom_field_definitions cfd
LEFT JOIN custom_field_values cfv
  ON cfv.field_id = cfd.id
  AND cfv.entity_type = 'contact'
  AND cfv.entity_id = '<contact_id>'
WHERE cfd.entity_type = 'contact'
ORDER BY cfd.position;
```

## Calendar

### Upcoming events for a user

```sql
SELECT
  e.title,
  e.starts_at,
  e.ends_at,
  e.location,
  ea.response
FROM events e
JOIN event_attendees ea ON ea.event_id = e.id
WHERE ea.user_id = '<user_id>'
  AND e.starts_at > now()
  AND e.status != 'cancelled'
ORDER BY e.starts_at ASC
LIMIT 20;
```
