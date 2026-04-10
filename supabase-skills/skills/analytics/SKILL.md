---
name: analytics
description: Tags, custom fields, and activity log for cross-cutting entity data
---

# Analytics

Tags, custom fields, and an activity log. A cross-cutting data layer that can attach labels, user-defined fields, and audit history to any entity type.

## Tables

### tags

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated |
| org_id | uuid | References organizations(id), cascade delete |
| name | text | Tag label, unique per org |
| color | text | Optional display color |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Auto-updated on modification |
| metadata | jsonb | Arbitrary key-value data |

### taggings

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated |
| org_id | uuid | References organizations(id), cascade delete |
| tag_id | uuid | References tags(id), cascade delete |
| entity_type | text | Target entity kind (contact, company, deal, task, ticket, document, project, event) |
| entity_id | uuid | ID of the tagged entity |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Auto-updated on modification |
| metadata | jsonb | Arbitrary key-value data |

### custom_field_definitions

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated |
| org_id | uuid | References organizations(id), cascade delete |
| entity_type | text | Which entity type this field applies to (contact, company, deal, task, ticket, document, project) |
| name | text | Field label, unique per org and entity type |
| field_type | field_type | Data type for this field, defaults to text |
| description | text | Optional explanation of the field |
| is_required | boolean | Whether a value is mandatory, defaults to false |
| options | jsonb | Allowed values for select and multi_select fields |
| position | integer | Display order, defaults to 0 |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Auto-updated on modification |
| metadata | jsonb | Arbitrary key-value data |

### custom_field_values

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated |
| org_id | uuid | References organizations(id), cascade delete |
| field_id | uuid | References custom_field_definitions(id), cascade delete |
| entity_type | text | Target entity kind (contact, company, deal, task, ticket, document, project) |
| entity_id | uuid | ID of the entity this value belongs to |
| value_text | text | Text value column |
| value_number | numeric | Numeric value column |
| value_boolean | boolean | Boolean value column |
| value_date | date | Date value column |
| value_json | jsonb | JSON value column (for select, multi_select, etc.) |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Auto-updated on modification |
| metadata | jsonb | Arbitrary key-value data |

### activities

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated |
| org_id | uuid | References organizations(id), cascade delete |
| actor_id | uuid | References users(id), set null on delete. NULL for system-generated activities |
| entity_type | text | Target entity kind (contact, company, deal, task, ticket, document, project, subscription, invoice, event) |
| entity_id | uuid | ID of the entity this activity relates to |
| action | activity_action | What happened |
| description | text | Human-readable summary |
| changes | jsonb | JSON diff, e.g. {"status": {"from": "open", "to": "closed"}} |
| occurred_at | timestamptz | When the action took place. Can differ from created_at for imported data |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Auto-updated on modification |
| metadata | jsonb | Arbitrary key-value data |

## Enums

### field_type

| Value | Description |
|-------|-------------|
| text | Free-form text |
| number | Numeric value |
| boolean | True or false |
| date | Calendar date |
| select | Single choice from a list of options |
| multi_select | Multiple choices from a list of options |
| url | URL string |
| email | Email address string |

### activity_action

| Value | Description |
|-------|-------------|
| created | Entity was created |
| updated | Entity was updated |
| deleted | Entity was deleted |
| status_changed | Status field changed |
| assigned | Entity was assigned to a user |
| commented | A comment was added |
| viewed | Entity was viewed |
| email_sent | An email was sent |
| email_received | An email was received |
| note_added | A note was attached |
| call_logged | A phone call was recorded |
| stage_changed | Pipeline stage changed |
| deal_won | Deal marked as won |
| deal_lost | Deal marked as lost |
| task_completed | Task marked as done |
| payment_received | Payment was received |

## Row-Level Security

All five tables are scoped to the current user's organization via `get_user_org_id()`. Select, insert, and update are allowed for any org member. Delete requires the `is_admin()` check.

## Dependencies

- identity -- organizations and users tables, `get_user_org_id()` and `is_admin()` functions, `set_updated_at()` trigger function

## Example Queries

Activity feed for a contact:

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

Get all tags for an entity:

```sql
SELECT t.name, t.color
FROM tags t
JOIN taggings tg ON tg.tag_id = t.id
WHERE tg.entity_type = 'deal' AND tg.entity_id = '<deal_id>';
```

Get custom field values for a contact:

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

Cross-entity activity feed for a deal and its related contact and company:

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

Find entities with a specific tag:

```sql
SELECT tg.entity_type, tg.entity_id, tg.created_at
FROM taggings tg
JOIN tags t ON t.id = tg.tag_id
WHERE t.name = 'VIP'
ORDER BY tg.created_at DESC;
```

Count activities by action type in the last 30 days:

```sql
SELECT
  action,
  count(*) AS total
FROM activities
WHERE occurred_at >= now() - interval '30 days'
GROUP BY action
ORDER BY total DESC;
```
