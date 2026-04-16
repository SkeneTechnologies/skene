---
name: campaigns
description: Campaigns, segments, lists, sends, and engagement events for email and multi-channel outreach.
---

# Campaigns

Campaigns, audience segments, recipient lists, per-contact send tracking, and engagement events (opens, clicks, bounces). Supports email and other channels via the `channel` column.

## Tables

### campaigns

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| creator_id | uuid | References users. Set NULL on user delete. |
| name | text | Campaign name. |
| subject | text | Email subject line or message headline. |
| body | text | Campaign content body. |
| channel | text | Delivery channel: email, sms, push, etc. Defaults to email. |
| status | campaign_status | Current campaign state. Defaults to draft. |
| scheduled_at | timestamptz | When the campaign is scheduled to send. |
| sent_at | timestamptz | When the campaign was actually sent. |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

### campaign_segments

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| name | text | Segment name. |
| description | text | Optional description of the segment criteria. |
| filter_rules | jsonb | JSON filter criteria used to resolve matching contacts. Defaults to empty object. |
| contact_count | integer | Cached count of contacts matching the segment. Defaults to 0. |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

### campaign_lists

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| campaign_id | uuid | References campaigns. Cascade delete. |
| segment_id | uuid | References campaign_segments. Set NULL on segment delete. |
| contact_id | uuid | References contacts. Cascade delete. |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

Unique constraint on (campaign_id, contact_id) -- a contact can appear in a campaign list only once.

### campaign_sends

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| campaign_id | uuid | References campaigns. Cascade delete. |
| contact_id | uuid | References contacts. Cascade delete. |
| status | send_status | Delivery status. Defaults to queued. |
| sent_at | timestamptz | When the message was sent. |
| delivered_at | timestamptz | When delivery was confirmed. |
| error | text | Error message if delivery failed. |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

### campaign_events

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| send_id | uuid | References campaign_sends. Cascade delete. |
| event_type | campaign_event_type | Type of engagement event. |
| url | text | Clicked URL for click events. NULL for other event types. |
| occurred_at | timestamptz | When the event occurred. Defaults to now(). |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

## Enums

### campaign_status

| Value | Description |
|-------|-------------|
| draft | Campaign is being composed. |
| scheduled | Campaign is scheduled for future delivery. |
| sending | Campaign is currently being sent. |
| sent | Campaign has been fully sent. |
| paused | Campaign sending has been paused. |
| canceled | Campaign has been canceled. |

### send_status

| Value | Description |
|-------|-------------|
| queued | Message is queued for delivery. |
| sent | Message has been sent to the provider. |
| delivered | Delivery confirmed by the provider. |
| bounced | Message bounced. |
| failed | Delivery failed due to an error. |

### campaign_event_type

| Value | Description |
|-------|-------------|
| open | Recipient opened the message. |
| click | Recipient clicked a link. |
| unsubscribe | Recipient unsubscribed. |
| complaint | Recipient reported the message as spam. |
| bounce | Message bounced (hard or soft). |

## Row-Level Security

All five tables are scoped to the current user's organization via `get_user_org_id()`. Any org member can select, insert, and update rows. Only admins (checked via `is_admin()`) can delete rows.

## Dependencies

- **crm** -- contacts
- **identity** (transitive via crm) -- organizations, users, `get_user_org_id()`, `is_admin()`, `set_updated_at()`

## Example Queries

Calculate open rate and click rate for a campaign:

```sql
SELECT
  c.name AS campaign,
  count(DISTINCT cs.id) AS total_sends,
  count(DISTINCT cs.id) FILTER (WHERE cs.status = 'delivered') AS delivered,
  count(DISTINCT ce.id) FILTER (WHERE ce.event_type = 'open') AS opens,
  count(DISTINCT ce.id) FILTER (WHERE ce.event_type = 'click') AS clicks,
  round(
    100.0 * count(DISTINCT ce.send_id) FILTER (WHERE ce.event_type = 'open')
    / nullif(count(DISTINCT cs.id) FILTER (WHERE cs.status = 'delivered'), 0),
    1
  ) AS open_rate_pct,
  round(
    100.0 * count(DISTINCT ce.send_id) FILTER (WHERE ce.event_type = 'click')
    / nullif(count(DISTINCT cs.id) FILTER (WHERE cs.status = 'delivered'), 0),
    1
  ) AS click_rate_pct
FROM campaigns c
JOIN campaign_sends cs ON cs.campaign_id = c.id
LEFT JOIN campaign_events ce ON ce.send_id = cs.id
WHERE c.id = '<campaign_id>'
GROUP BY c.id, c.name;
```

Show bounce rate by campaign:

```sql
SELECT
  c.name AS campaign,
  count(cs.id) AS total_sends,
  count(cs.id) FILTER (WHERE cs.status = 'bounced') AS bounced,
  round(
    100.0 * count(cs.id) FILTER (WHERE cs.status = 'bounced')
    / nullif(count(cs.id), 0),
    1
  ) AS bounce_rate_pct
FROM campaigns c
JOIN campaign_sends cs ON cs.campaign_id = c.id
WHERE c.status = 'sent'
GROUP BY c.id, c.name
ORDER BY bounce_rate_pct DESC;
```

List engagement events for a specific contact across all campaigns:

```sql
SELECT
  c.name AS campaign,
  ce.event_type,
  ce.url,
  ce.occurred_at
FROM campaign_events ce
JOIN campaign_sends cs ON cs.id = ce.send_id
JOIN campaigns c ON c.id = cs.campaign_id
WHERE cs.contact_id = '<contact_id>'
ORDER BY ce.occurred_at DESC;
```

Show segment sizes and how many campaigns each segment has been used in:

```sql
SELECT
  seg.name AS segment,
  seg.contact_count,
  count(DISTINCT cl.campaign_id) AS campaigns_used_in
FROM campaign_segments seg
LEFT JOIN campaign_lists cl ON cl.segment_id = seg.id
GROUP BY seg.id, seg.name, seg.contact_count
ORDER BY seg.contact_count DESC;
```

List campaigns with delivery summary (queued, sent, delivered, bounced, failed):

```sql
SELECT
  c.name AS campaign,
  c.status,
  c.sent_at,
  count(cs.id) FILTER (WHERE cs.status = 'queued') AS queued,
  count(cs.id) FILTER (WHERE cs.status = 'sent') AS sent,
  count(cs.id) FILTER (WHERE cs.status = 'delivered') AS delivered,
  count(cs.id) FILTER (WHERE cs.status = 'bounced') AS bounced,
  count(cs.id) FILTER (WHERE cs.status = 'failed') AS failed
FROM campaigns c
LEFT JOIN campaign_sends cs ON cs.campaign_id = c.id
GROUP BY c.id, c.name, c.status, c.sent_at
ORDER BY c.sent_at DESC NULLS LAST;
```

Find contacts who clicked a link in any campaign but never unsubscribed:

```sql
SELECT DISTINCT
  con.id,
  con.first_name,
  con.last_name,
  con.email
FROM contacts con
JOIN campaign_sends cs ON cs.contact_id = con.id
JOIN campaign_events ce ON ce.send_id = cs.id AND ce.event_type = 'click'
WHERE con.id NOT IN (
  SELECT cs2.contact_id
  FROM campaign_sends cs2
  JOIN campaign_events ce2 ON ce2.send_id = cs2.id AND ce2.event_type = 'unsubscribe'
)
ORDER BY con.last_name, con.first_name;
```
