---
name: calendar
description: Events and attendees with optional polymorphic links to CRM records.
---

# Calendar

Events with attendees, supporting all-day events, recurrence rules (iCal RRULE), and optional polymorphic links to contacts, companies, deals, tickets, or projects. The event_attendees table intentionally has no foreign key constraint on contact_id, so the calendar skill works without the CRM skill installed.

## Tables

### events

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| creator_id | uuid | References users. Set NULL on user delete. |
| entity_type | text | Optional polymorphic link type. Constrained to: contact, company, deal, ticket, project. |
| entity_id | uuid | ID of the linked record. |
| title | text | Event title. |
| description | text | Optional event description. |
| location | text | Optional location string. |
| status | event_status | Event state. Defaults to confirmed. |
| starts_at | timestamptz | Event start time. |
| ends_at | timestamptz | Event end time. |
| all_day | boolean | Whether this is an all-day event. Defaults to false. |
| recurrence_rule | text | iCal RRULE string for recurring events. |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

### event_attendees

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| event_id | uuid | References events. Cascade delete. |
| user_id | uuid | References users. Cascade delete. At least one of user_id or contact_id is required. |
| contact_id | uuid | References contacts if CRM is installed. No FK constraint. At least one of user_id or contact_id is required. |
| response | attendee_response | RSVP status. Defaults to pending. |
| is_organizer | boolean | Whether this attendee is the event organizer. Defaults to false. |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

## Enums

### event_status

| Value | Description |
|-------|-------------|
| confirmed | Event is confirmed and will take place. |
| tentative | Event is tentatively scheduled. |
| cancelled | Event has been cancelled. |

### attendee_response

| Value | Description |
|-------|-------------|
| accepted | Attendee has accepted the invitation. |
| declined | Attendee has declined the invitation. |
| tentative | Attendee has tentatively accepted. |
| pending | Attendee has not yet responded. |

## Row-Level Security

Both tables are scoped to the current user's organization via `get_user_org_id()`. Any org member can select, insert, and update rows. Only admins (checked via `is_admin()`) can delete events or attendees.

## Dependencies

- **identity** -- organizations, users, `get_user_org_id()`, `is_admin()`, `set_updated_at()`

## Example Queries

Fetch upcoming events for a specific user:

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

List all attendees for a given event, showing both internal users and external contacts:

```sql
SELECT
  ea.id,
  ea.response,
  ea.is_organizer,
  u.full_name AS user_name,
  ea.contact_id
FROM event_attendees ea
LEFT JOIN users u ON u.id = ea.user_id
WHERE ea.event_id = '<event_id>'
ORDER BY ea.is_organizer DESC, u.full_name ASC;
```

Find events within a date range (e.g. a calendar week view):

```sql
SELECT
  id,
  title,
  starts_at,
  ends_at,
  all_day,
  status,
  location
FROM events
WHERE starts_at < '<range_end>'::timestamptz
  AND ends_at > '<range_start>'::timestamptz
  AND status != 'cancelled'
ORDER BY starts_at ASC;
```

Count events per day for the current month:

```sql
SELECT
  date_trunc('day', starts_at)::date AS event_date,
  count(*) AS event_count
FROM events
WHERE starts_at >= date_trunc('month', now())
  AND starts_at < date_trunc('month', now()) + interval '1 month'
  AND status != 'cancelled'
GROUP BY event_date
ORDER BY event_date;
```

List events linked to a specific CRM record (e.g. a deal):

```sql
SELECT
  id,
  title,
  starts_at,
  ends_at,
  status,
  creator_id
FROM events
WHERE entity_type = 'deal'
  AND entity_id = '<deal_id>'
ORDER BY starts_at DESC;
```
