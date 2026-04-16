---
name: forms
description: Form definitions, fields, submissions, and file uploads with RLS
---

# Forms

Configurable forms with ordered fields, submission tracking, and file uploads -- all scoped by organization with row-level security. Depends on the identity skill for organizations and users.

## Tables

### form_definitions

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| org_id | uuid | FK to organizations |
| creator_id | uuid | FK to users. The user who created the form. NULL if creator was deleted |
| name | text | Human-readable form name |
| slug | text | URL-safe identifier, unique per org |
| description | text | Optional description shown to respondents |
| status | form_status | Lifecycle state: draft, active, or archived |
| submit_message | text | Confirmation message shown after submission |
| redirect_url | text | Optional URL to redirect to after submission |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Last update timestamp (auto-set by trigger) |
| metadata | jsonb | Arbitrary JSON for form-level settings |

Unique constraint on (org_id, slug).

### form_fields

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| org_id | uuid | FK to organizations |
| form_id | uuid | FK to form_definitions |
| label | text | Display label shown to the respondent |
| field_key | text | Machine-readable key stored in submission data JSON |
| field_type | form_field_type | Input type: text, email, number, select, multiselect, checkbox, textarea, date, or file |
| position | integer | Display order within the form. Lower values appear first |
| is_required | boolean | Whether the field must be filled before submission |
| options | jsonb | Option objects for select/multiselect fields |
| validation | jsonb | Validation rules, e.g. {"min_length": 3, "max_length": 500} |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Last update timestamp (auto-set by trigger) |
| metadata | jsonb | Arbitrary JSON |

Unique constraint on (form_id, field_key).

### form_submissions

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| org_id | uuid | FK to organizations |
| form_id | uuid | FK to form_definitions |
| contact_id | uuid | Optional reference to a CRM contact (not enforced as FK) |
| data | jsonb | JSON object mapping field_key to submitted value |
| submitted_at | timestamptz | When the respondent submitted the form |
| ip_address | inet | IP address of the respondent |
| user_agent | text | Browser user agent string |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Last update timestamp (auto-set by trigger) |
| metadata | jsonb | Arbitrary JSON |

### form_uploads

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| org_id | uuid | FK to organizations |
| submission_id | uuid | FK to form_submissions |
| field_id | uuid | FK to form_fields. NULL if originating field was deleted |
| file_name | text | Original file name |
| file_size | bigint | File size in bytes |
| mime_type | text | MIME type of the uploaded file |
| storage_path | text | Path within Supabase Storage |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Last update timestamp (auto-set by trigger) |
| metadata | jsonb | Arbitrary JSON |

## Enums

### form_status

| Value | Description |
|-------|-------------|
| draft | Not yet accepting submissions |
| active | Accepting submissions |
| archived | No longer accepting submissions, kept for reference |

### form_field_type

| Value | Description |
|-------|-------------|
| text | Single-line text input |
| email | Email address input |
| number | Numeric input |
| select | Single-choice dropdown |
| multiselect | Multi-choice dropdown |
| checkbox | Boolean checkbox |
| textarea | Multi-line text input |
| date | Date picker |
| file | File upload |

## Row-Level Security

All tables have RLS enabled and are scoped to the current user's organization via `get_user_org_id()`.

- **form_definitions**: SELECT/INSERT/UPDATE for own org. DELETE requires admin.
- **form_fields**: SELECT/INSERT/UPDATE for own org. DELETE requires admin.
- **form_submissions**: SELECT/INSERT/UPDATE for own org. DELETE requires admin.
- **form_uploads**: SELECT/INSERT/UPDATE for own org. DELETE requires admin.

## Dependencies

- identity -- organizations, users

## Example Queries

List all active forms in the current organization:

```sql
SELECT fd.id, fd.name, fd.slug, fd.status,
       count(fs.id) AS submission_count
FROM form_definitions fd
LEFT JOIN form_submissions fs ON fs.form_id = fd.id
WHERE fd.org_id = get_user_org_id()
  AND fd.status = 'active'
GROUP BY fd.id
ORDER BY fd.name;
```

Get a form with its fields in display order:

```sql
SELECT fd.name AS form_name,
       ff.label, ff.field_key, ff.field_type, ff.is_required, ff.position
FROM form_definitions fd
JOIN form_fields ff ON ff.form_id = fd.id
WHERE fd.slug = 'contact-us'
  AND fd.org_id = get_user_org_id()
ORDER BY ff.position;
```

Retrieve submissions for a form with submitted values:

```sql
SELECT fs.id, fs.submitted_at, fs.data, fs.ip_address
FROM form_submissions fs
WHERE fs.form_id = '<form_id>'
  AND fs.org_id = get_user_org_id()
ORDER BY fs.submitted_at DESC
LIMIT 50;
```

Count submissions per form grouped by day:

```sql
SELECT fd.name,
       date_trunc('day', fs.submitted_at) AS day,
       count(*) AS submissions
FROM form_submissions fs
JOIN form_definitions fd ON fd.id = fs.form_id
WHERE fs.org_id = get_user_org_id()
GROUP BY fd.name, day
ORDER BY day DESC;
```

List all uploads for a given submission:

```sql
SELECT fu.file_name, fu.file_size, fu.mime_type, fu.storage_path,
       ff.label AS field_label
FROM form_uploads fu
LEFT JOIN form_fields ff ON ff.id = fu.field_id
WHERE fu.submission_id = '<submission_id>'
  AND fu.org_id = get_user_org_id()
ORDER BY fu.created_at;
```

Calculate NPS score from survey submissions:

```sql
SELECT
  count(*) FILTER (WHERE (data->>'score')::int >= 9)  AS promoters,
  count(*) FILTER (WHERE (data->>'score')::int BETWEEN 7 AND 8) AS passives,
  count(*) FILTER (WHERE (data->>'score')::int <= 6)  AS detractors,
  round(
    100.0 * (
      count(*) FILTER (WHERE (data->>'score')::int >= 9)
      - count(*) FILTER (WHERE (data->>'score')::int <= 6)
    ) / nullif(count(*), 0),
    1
  ) AS nps
FROM form_submissions
WHERE form_id = '<nps_form_id>'
  AND org_id = get_user_org_id();
```
