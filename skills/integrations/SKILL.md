---
name: integrations
description: Connected apps, OAuth tokens, webhooks, and sync logs
---

# Integrations

Connected apps, OAuth tokens, webhooks, and sync logs. Manages third-party connections, credential storage, outgoing webhook delivery, and data synchronization tracking.

## Tables

### connected_apps

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated |
| org_id | uuid | References organizations(id), cascade delete |
| name | text | Display name of the connected app |
| provider | text | Provider identifier (slack, hubspot, stripe, etc.) |
| status | integration_status | Connection health status, defaults to active |
| config | jsonb | Provider-specific configuration |
| connected_by | uuid | References users(id), set null on delete |
| connected_at | timestamptz | When the connection was established |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Auto-updated on modification |
| metadata | jsonb | Arbitrary key-value data |

### oauth_tokens

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated |
| org_id | uuid | References organizations(id), cascade delete |
| app_id | uuid | References connected_apps(id), cascade delete |
| user_id | uuid | References users(id), cascade delete |
| access_token_enc | text | Encrypted access token |
| refresh_token_enc | text | Encrypted refresh token (optional) |
| token_type | text | Token type, defaults to bearer |
| scopes | text[] | Granted OAuth scopes |
| expires_at | timestamptz | Token expiration time |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Auto-updated on modification |
| metadata | jsonb | Arbitrary key-value data |

### webhooks

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated |
| org_id | uuid | References organizations(id), cascade delete |
| url | text | Destination URL for webhook delivery |
| secret | text | Signing secret for payload verification |
| events | text[] | Event types this webhook subscribes to |
| is_active | boolean | Whether the webhook is enabled, defaults to true |
| created_by | uuid | References users(id), set null on delete |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Auto-updated on modification |
| metadata | jsonb | Arbitrary key-value data |

### webhook_events

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated |
| org_id | uuid | References organizations(id), cascade delete |
| webhook_id | uuid | References webhooks(id), cascade delete |
| event_type | text | The type of event that triggered delivery |
| payload | jsonb | Event payload sent to the endpoint |
| status | webhook_event_status | Delivery status, defaults to pending |
| response_code | smallint | HTTP response code from the endpoint |
| attempts | integer | Number of delivery attempts, defaults to 0 |
| last_attempt_at | timestamptz | Timestamp of the most recent attempt |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Auto-updated on modification |
| metadata | jsonb | Arbitrary key-value data |

### sync_logs

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated |
| org_id | uuid | References organizations(id), cascade delete |
| app_id | uuid | References connected_apps(id), cascade delete |
| direction | sync_direction | Whether the sync is inbound or outbound |
| entity_type | text | Type of entity being synced (contacts, deals, etc.) |
| entity_id | uuid | Optional specific entity being synced |
| status | sync_status | Current sync status, defaults to pending |
| records_processed | integer | Number of records handled, defaults to 0 |
| records_failed | integer | Number of records that failed, defaults to 0 |
| started_at | timestamptz | When the sync run began |
| completed_at | timestamptz | When the sync run finished |
| error | text | Error details if the sync failed |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Auto-updated on modification |
| metadata | jsonb | Arbitrary key-value data |

## Enums

### integration_status

| Value | Description |
|-------|-------------|
| active | Connection is healthy and operational |
| inactive | Connection is disabled |
| error | Connection has a problem that needs attention |

### webhook_event_status

| Value | Description |
|-------|-------------|
| pending | Event is queued for delivery |
| sent | Event was delivered successfully |
| failed | Delivery failed after all retry attempts |

### sync_direction

| Value | Description |
|-------|-------------|
| inbound | Data flowing from the external app into the platform |
| outbound | Data flowing from the platform to the external app |

### sync_status

| Value | Description |
|-------|-------------|
| pending | Sync is queued but has not started |
| running | Sync is currently executing |
| completed | Sync finished successfully |
| failed | Sync finished with an error |

## Row-Level Security

All five tables are scoped to the current user's organization via `get_user_org_id()`. Select, insert, and update are allowed for any org member. Delete requires the `is_admin()` check.

## Dependencies

- identity -- organizations and users tables, `get_user_org_id()` and `is_admin()` functions, `set_updated_at()` trigger function

## Example Queries

List all active connected apps for the current org:

```sql
SELECT id, name, provider, status, connected_at
FROM connected_apps
WHERE status = 'active'
ORDER BY connected_at DESC;
```

Webhook delivery status summary (last 30 days):

```sql
SELECT
  w.url,
  count(we.id) AS total_events,
  count(we.id) FILTER (WHERE we.status = 'sent') AS delivered,
  count(we.id) FILTER (WHERE we.status = 'failed') AS failed,
  count(we.id) FILTER (WHERE we.status = 'pending') AS pending
FROM webhooks w
LEFT JOIN webhook_events we ON we.webhook_id = w.id
  AND we.created_at >= now() - interval '30 days'
WHERE w.is_active = true
GROUP BY w.id, w.url
ORDER BY w.url;
```

Sync history for a specific app:

```sql
SELECT
  sl.direction,
  sl.entity_type,
  sl.status,
  sl.records_processed,
  sl.records_failed,
  sl.started_at,
  sl.completed_at,
  sl.error
FROM sync_logs sl
WHERE sl.app_id = '<app_id>'
ORDER BY sl.started_at DESC
LIMIT 20;
```

Failed syncs in the last 7 days:

```sql
SELECT
  ca.name AS app_name,
  sl.direction,
  sl.entity_type,
  sl.error,
  sl.started_at
FROM sync_logs sl
JOIN connected_apps ca ON ca.id = sl.app_id
WHERE sl.status = 'failed'
  AND sl.started_at >= now() - interval '7 days'
ORDER BY sl.started_at DESC;
```

Active integrations with token expiration status:

```sql
SELECT
  ca.name AS app_name,
  ca.provider,
  ot.user_id,
  ot.scopes,
  ot.expires_at,
  CASE
    WHEN ot.expires_at < now() THEN 'expired'
    WHEN ot.expires_at < now() + interval '7 days' THEN 'expiring_soon'
    ELSE 'valid'
  END AS token_status
FROM connected_apps ca
JOIN oauth_tokens ot ON ot.app_id = ca.id
WHERE ca.status = 'active'
ORDER BY ot.expires_at ASC;
```

Failed webhook events awaiting retry:

```sql
SELECT
  w.url,
  we.event_type,
  we.attempts,
  we.response_code,
  we.last_attempt_at,
  we.payload
FROM webhook_events we
JOIN webhooks w ON w.id = we.webhook_id
WHERE we.status = 'failed'
ORDER BY we.last_attempt_at DESC;
```
