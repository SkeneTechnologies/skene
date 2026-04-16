---
name: notifications
description: Notification templates, deliveries, preferences, and push tokens with RLS
---

# Notifications

Multi-channel notification system with reusable templates, delivery tracking, per-user preferences, and device push tokens -- all scoped by organization with row-level security. Depends on the identity skill for organizations and users.

## Tables

### notification_templates

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| org_id | uuid | FK to organizations |
| name | text | Human-readable template name |
| slug | text | URL-safe identifier, unique per org. Used to look up templates in code |
| channel | notification_channel | Delivery channel: email, sms, push, or in_app |
| subject | text | Subject line for email notifications. NULL for push/in_app |
| body_template | text | Template string with placeholder variables, e.g. "Hello {{name}}" |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Last update timestamp (auto-set by trigger) |
| metadata | jsonb | Arbitrary JSON for template-level settings |

Unique constraint on (org_id, slug).

### notification_deliveries

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| org_id | uuid | FK to organizations |
| template_id | uuid | FK to notification_templates. NULL if template was deleted |
| user_id | uuid | FK to users. The recipient |
| channel | notification_channel | Channel used for this delivery |
| subject | text | Rendered subject line |
| body | text | Rendered body content |
| status | delivery_status | Lifecycle state: queued, sent, delivered, failed, or read |
| sent_at | timestamptz | When the notification was dispatched |
| read_at | timestamptz | When the recipient opened or read the notification |
| error | text | Error message if delivery failed. NULL on success |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Last update timestamp (auto-set by trigger) |
| metadata | jsonb | Arbitrary JSON |

### notification_preferences

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| org_id | uuid | FK to organizations |
| user_id | uuid | FK to users |
| channel | notification_channel | Channel this preference applies to |
| category | text | Notification category, e.g. "marketing", "billing", "general" |
| is_enabled | boolean | Whether the user wants to receive notifications for this channel and category |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Last update timestamp (auto-set by trigger) |
| metadata | jsonb | Arbitrary JSON |

Unique constraint on (user_id, channel, category).

### push_tokens

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| org_id | uuid | FK to organizations |
| user_id | uuid | FK to users |
| token | text | Device push token string |
| platform | push_platform | Platform: ios, android, or web |
| device_name | text | Human-readable device name |
| is_active | boolean | Set to false when the token is expired or revoked |
| last_used_at | timestamptz | Timestamp of last successful push delivery |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Last update timestamp (auto-set by trigger) |
| metadata | jsonb | Arbitrary JSON |

Unique constraint on (user_id, token).

## Enums

### notification_channel

| Value | Description |
|-------|-------------|
| email | Email delivery |
| sms | SMS text message |
| push | Native push notification (iOS, Android, or web) |
| in_app | In-application notification shown in the UI |

### delivery_status

| Value | Description |
|-------|-------------|
| queued | Waiting to be sent |
| sent | Dispatched to the delivery provider |
| delivered | Confirmed delivered to the recipient |
| failed | Delivery failed. Check the error column for details |
| read | Opened or read by the recipient |

### push_platform

| Value | Description |
|-------|-------------|
| ios | Apple Push Notification service |
| android | Firebase Cloud Messaging |
| web | Web Push API |

## Row-Level Security

All tables have RLS enabled and are scoped to the current user's organization via `get_user_org_id()`.

- **notification_templates**: SELECT/INSERT/UPDATE for own org. DELETE requires admin.
- **notification_deliveries**: SELECT/INSERT/UPDATE for own org. DELETE requires admin.
- **notification_preferences**: SELECT/INSERT/UPDATE for own org. DELETE requires admin.
- **push_tokens**: SELECT/INSERT/UPDATE for own org. DELETE requires admin.

## Dependencies

- identity -- organizations, users

## Example Queries

Get unread in-app notifications for the current user:

```sql
SELECT nd.id, nd.body, nd.created_at
FROM notification_deliveries nd
JOIN users u ON u.id = nd.user_id
WHERE u.auth_id = auth.uid()
  AND nd.channel = 'in_app'
  AND nd.status != 'read'
ORDER BY nd.created_at DESC;
```

Count notifications by status for a given channel:

```sql
SELECT nd.status, count(*) AS total
FROM notification_deliveries nd
WHERE nd.org_id = get_user_org_id()
  AND nd.channel = 'email'
GROUP BY nd.status
ORDER BY total DESC;
```

Check a user's notification preferences:

```sql
SELECT np.channel, np.category, np.is_enabled
FROM notification_preferences np
WHERE np.user_id = '<user_id>'
  AND np.org_id = get_user_org_id()
ORDER BY np.channel, np.category;
```

Find all active push tokens for a user:

```sql
SELECT pt.token, pt.platform, pt.device_name, pt.last_used_at
FROM push_tokens pt
WHERE pt.user_id = '<user_id>'
  AND pt.is_active = true
  AND pt.org_id = get_user_org_id()
ORDER BY pt.last_used_at DESC NULLS LAST;
```

Get delivery failure rate by template over the last 30 days:

```sql
SELECT nt.name AS template_name,
       count(*) AS total_sent,
       count(*) FILTER (WHERE nd.status = 'failed') AS failed,
       round(
         100.0 * count(*) FILTER (WHERE nd.status = 'failed') / nullif(count(*), 0),
         1
       ) AS failure_pct
FROM notification_deliveries nd
JOIN notification_templates nt ON nt.id = nd.template_id
WHERE nd.org_id = get_user_org_id()
  AND nd.created_at >= now() - interval '30 days'
GROUP BY nt.name
ORDER BY failure_pct DESC;
```

List users who have opted out of email notifications:

```sql
SELECT u.full_name, u.email, np.category
FROM notification_preferences np
JOIN users u ON u.id = np.user_id
WHERE np.org_id = get_user_org_id()
  AND np.channel = 'email'
  AND np.is_enabled = false
ORDER BY u.full_name;
```
