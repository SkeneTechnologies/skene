---
name: crm
description: Contacts, companies, and contact-company relationships for customer management
---

# CRM

Contacts, companies, and the many-to-many relationship between them. Contacts represent external people you do business with (not application users). Companies represent the organizations those contacts belong to.

## Tables

### contacts

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| org_id | uuid | FK to organizations |
| owner_id | uuid | FK to users. The user responsible for this contact |
| first_name | text | Contact first name |
| last_name | text | Contact last name |
| email | text | Email address |
| phone | text | Phone number |
| type | contact_type | Lifecycle stage: lead, prospect, customer, partner, or other |
| title | text | Job title |
| source | text | How this contact was acquired (e.g. website, referral, trade show) |
| avatar_url | text | URL to avatar image |
| address_line1 | text | Street address line 1 |
| address_line2 | text | Street address line 2 |
| city | text | City |
| state | text | State or province |
| postal_code | text | Postal or zip code |
| country | text | Country |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Last update timestamp (auto-set by trigger) |
| metadata | jsonb | Arbitrary JSON |

### companies

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| org_id | uuid | FK to organizations |
| owner_id | uuid | FK to users. The user responsible for this company |
| name | text | Company name |
| domain | text | Company web domain |
| industry | text | Industry vertical |
| size | text | Company size bracket (e.g. 1-10, 11-50, 51-200) |
| website | text | Full website URL |
| phone | text | Phone number |
| address_line1 | text | Street address line 1 |
| address_line2 | text | Street address line 2 |
| city | text | City |
| state | text | State or province |
| postal_code | text | Postal or zip code |
| country | text | Country |
| annual_revenue | numeric | Estimated annual revenue in cents or smallest currency unit |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Last update timestamp (auto-set by trigger) |
| metadata | jsonb | Arbitrary JSON |

### contact_companies

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| org_id | uuid | FK to organizations |
| contact_id | uuid | FK to contacts |
| company_id | uuid | FK to companies |
| title | text | Contact's role or title at this company |
| is_primary | boolean | Whether this is the contact's current primary company |
| started_at | date | When the contact started at this company |
| ended_at | date | When the contact left this company |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Last update timestamp (auto-set by trigger) |
| metadata | jsonb | Arbitrary JSON |

Unique constraint on (contact_id, company_id).

## Enums

### contact_type

| Value | Description |
|-------|-------------|
| lead | Initial contact, not yet qualified |
| prospect | Qualified and actively being pursued |
| customer | Converted to a paying customer |
| partner | Business partner or collaborator |
| other | Does not fit the other categories |

## Row-Level Security

All tables have RLS enabled and are scoped to the current user's organization via `get_user_org_id()`.

- **contacts**: SELECT/INSERT/UPDATE for own org. DELETE requires admin.
- **companies**: SELECT/INSERT/UPDATE for own org. DELETE requires admin.
- **contact_companies**: SELECT/INSERT/UPDATE for own org. DELETE requires admin.

## Dependencies

- `identity` -- organizations, users, and RLS helper functions

## Example Queries

Get all contacts at a specific company:

```sql
SELECT c.first_name, c.last_name, c.email, cc.title
FROM contacts c
JOIN contact_companies cc ON cc.contact_id = c.id
WHERE cc.company_id = '<company_id>'
  AND cc.is_primary = true
ORDER BY c.last_name;
```

Search contacts by type with company info:

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

List all companies with their primary contact count:

```sql
SELECT
  co.name,
  co.industry,
  co.size,
  count(cc.id) AS contact_count
FROM companies co
LEFT JOIN contact_companies cc ON cc.company_id = co.id AND cc.is_primary = true
WHERE co.org_id = get_user_org_id()
GROUP BY co.id, co.name, co.industry, co.size
ORDER BY contact_count DESC;
```

Find contacts without a company association:

```sql
SELECT c.first_name, c.last_name, c.email, c.type, c.source
FROM contacts c
LEFT JOIN contact_companies cc ON cc.contact_id = c.id
WHERE c.org_id = get_user_org_id()
  AND cc.id IS NULL
ORDER BY c.created_at DESC;
```

Get a contact's full company history:

```sql
SELECT
  co.name AS company,
  cc.title,
  cc.started_at,
  cc.ended_at,
  cc.is_primary
FROM contact_companies cc
JOIN companies co ON co.id = cc.company_id
WHERE cc.contact_id = '<contact_id>'
ORDER BY cc.started_at DESC NULLS FIRST;
```
