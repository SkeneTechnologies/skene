---
name: comms
description: Polymorphic conversation threads and messages for any entity
---

# Comms

Conversation threads and messages that attach to any entity (contact, company, deal, ticket, task, or project) via a polymorphic relationship.

## Tables

### threads

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated |
| org_id | uuid | References organizations. CASCADE on delete |
| entity_type | text | What this thread attaches to. Checked against allowed values |
| entity_id | uuid | ID of the related entity. No FK enforced for polymorphism |
| subject | text | Optional thread subject line |
| channel | channel_type | Communication channel (email, sms, etc.) |
| is_closed | boolean | Whether the thread is closed, defaults to false |
| created_at | timestamptz | Row creation time |
| updated_at | timestamptz | Auto-updated on change via trigger |
| metadata | jsonb | Freeform JSON, defaults to empty object |

Allowed entity_type values: contact, company, deal, ticket, task, project.

### messages

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated |
| org_id | uuid | References organizations. CASCADE on delete |
| thread_id | uuid | References threads. CASCADE on delete |
| author_id | uuid | References users. SET NULL on delete |
| contact_id | uuid | References contacts. SET NULL on delete |
| direction | message_direction | Inbound, outbound, or internal. Defaults to 'internal' |
| body | text | Plain text message body (required) |
| html_body | text | Rich HTML version of the message body |
| external_id | text | ID from external system, e.g. email Message-ID |
| sent_at | timestamptz | When the message was sent, defaults to now() |
| created_at | timestamptz | Row creation time |
| updated_at | timestamptz | Auto-updated on change via trigger |
| metadata | jsonb | Freeform JSON, defaults to empty object |

## Enums

### message_direction

| Value | Description |
|-------|-------------|
| inbound | Message received from an external party |
| outbound | Message sent to an external party |
| internal | Internal note or comment |

### channel_type

Shared with the support skill. Defined with a guard (`CREATE TYPE IF NOT EXISTS` pattern) so it works whether or not support is installed.

| Value | Description |
|-------|-------------|
| email | Email channel |
| sms | SMS / text message |
| chat | Live chat or messaging |
| phone | Phone call |
| social | Social media |

## Row-Level Security

Both tables have RLS enabled and scoped to org_id via `get_user_org_id()`. SELECT, INSERT, and UPDATE are open to all org members. DELETE requires admin privileges via `is_admin()`.

## Dependencies

- crm (organizations, users, contacts)

## Example Queries

```sql
-- Full conversation history for a contact
SELECT
  th.entity_type,
  th.entity_id,
  m.direction,
  coalesce(u.full_name, c.first_name || ' ' || coalesce(c.last_name, '')) AS sender,
  m.body,
  m.sent_at
FROM threads th
JOIN messages m ON m.thread_id = th.id
LEFT JOIN users u ON u.id = m.author_id
LEFT JOIN contacts c ON c.id = m.contact_id
WHERE th.entity_type = 'contact' AND th.entity_id = '<contact_id>'
ORDER BY m.sent_at ASC;
```

```sql
-- Recent inbound messages across all threads
SELECT
  th.entity_type,
  th.entity_id,
  th.subject,
  th.channel,
  m.body,
  m.sent_at,
  c.first_name || ' ' || coalesce(c.last_name, '') AS from_contact
FROM messages m
JOIN threads th ON th.id = m.thread_id
LEFT JOIN contacts c ON c.id = m.contact_id
WHERE m.direction = 'inbound'
ORDER BY m.sent_at DESC
LIMIT 50;
```

```sql
-- Threads with no reply (inbound message but no outbound response)
SELECT
  th.id AS thread_id,
  th.entity_type,
  th.entity_id,
  th.subject,
  th.channel,
  min(m.sent_at) AS first_message_at
FROM threads th
JOIN messages m ON m.thread_id = th.id
WHERE th.is_closed = false
  AND m.direction = 'inbound'
  AND NOT EXISTS (
    SELECT 1 FROM messages m2
    WHERE m2.thread_id = th.id
      AND m2.direction = 'outbound'
      AND m2.sent_at > m.sent_at
  )
GROUP BY th.id, th.entity_type, th.entity_id, th.subject, th.channel
ORDER BY first_message_at ASC;
```

```sql
-- Message volume by channel and direction (last 30 days)
SELECT
  th.channel,
  count(*) FILTER (WHERE m.direction = 'inbound') AS inbound,
  count(*) FILTER (WHERE m.direction = 'outbound') AS outbound,
  count(*) FILTER (WHERE m.direction = 'internal') AS internal,
  count(*) AS total
FROM messages m
JOIN threads th ON th.id = m.thread_id
WHERE m.sent_at >= now() - interval '30 days'
GROUP BY th.channel
ORDER BY total DESC;
```

```sql
-- Open threads per entity type with message counts
SELECT
  th.entity_type,
  count(DISTINCT th.id) AS open_threads,
  count(m.id) AS total_messages,
  max(m.sent_at) AS last_activity
FROM threads th
LEFT JOIN messages m ON m.thread_id = th.id
WHERE th.is_closed = false
GROUP BY th.entity_type
ORDER BY open_threads DESC;
```
