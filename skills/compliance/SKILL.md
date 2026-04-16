---
name: compliance
description: Consent records, deletion requests, and retention policies
---

# Compliance

Consent records, deletion requests, and retention policies. Provides the data layer for GDPR, CCPA, and other privacy regulation compliance.

## Tables

### consent_records

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated |
| org_id | uuid | References organizations(id), cascade delete |
| entity_type | text | Type of entity granting consent (contact, user, etc.) |
| entity_id | uuid | Identifier of the entity granting consent |
| purpose | text | What the consent is for (marketing_email, analytics, etc.) |
| legal_basis | text | Legal basis for processing (consent, legitimate_interest, contract, etc.) |
| granted_at | timestamptz | When consent was given |
| revoked_at | timestamptz | When consent was revoked (null if still active) |
| expires_at | timestamptz | When consent expires (null if no expiry) |
| ip_address | inet | IP address at the time of consent |
| source | text | Where consent was collected (signup_form, web_form, import, etc.) |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Auto-updated on modification |
| metadata | jsonb | Arbitrary key-value data |

### deletion_requests

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated |
| org_id | uuid | References organizations(id), cascade delete |
| requester_type | text | Type of entity requesting deletion |
| requester_id | uuid | Identifier of the requester |
| status | deletion_status | Current status, defaults to requested |
| reason | text | Reason for the deletion request |
| requested_at | timestamptz | When the request was submitted |
| completed_at | timestamptz | When the request was fulfilled |
| completed_by | uuid | References users(id), set null on delete |
| notes | text | Internal notes about the request |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Auto-updated on modification |
| metadata | jsonb | Arbitrary key-value data |

### retention_policies

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated |
| org_id | uuid | References organizations(id), cascade delete |
| entity_type | text | Type of entity this policy applies to |
| retention_days | integer | Number of days to retain data |
| action | retention_action | What to do when retention period expires, defaults to archive |
| is_active | boolean | Whether this policy is enforced, defaults to true |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Auto-updated on modification |
| metadata | jsonb | Arbitrary key-value data |

## Enums

### deletion_status

| Value | Description |
|-------|-------------|
| requested | Deletion has been requested but not started |
| in_progress | Deletion is underway |
| completed | All requested data has been removed |
| rejected | Request was denied with documented reason |

### retention_action

| Value | Description |
|-------|-------------|
| delete | Permanently remove the data |
| anonymize | Strip personally identifiable fields |
| archive | Move to cold storage |

## Row-Level Security

All three tables are scoped to the current user's organization via `get_user_org_id()`. Select, insert, and update are allowed for any org member. Delete requires the `is_admin()` check.

## Dependencies

- identity -- organizations and users tables, `get_user_org_id()` and `is_admin()` functions, `set_updated_at()` trigger function

## Example Queries

Active consents for a specific contact:

```sql
SELECT id, purpose, legal_basis, granted_at, expires_at, source
FROM consent_records
WHERE entity_type = 'contact'
  AND entity_id = '<contact_id>'
  AND revoked_at IS NULL
  AND (expires_at IS NULL OR expires_at > now())
ORDER BY granted_at DESC;
```

Expired consents that need attention:

```sql
SELECT
  cr.id,
  cr.entity_type,
  cr.entity_id,
  cr.purpose,
  cr.expires_at
FROM consent_records cr
WHERE cr.revoked_at IS NULL
  AND cr.expires_at IS NOT NULL
  AND cr.expires_at < now()
ORDER BY cr.expires_at ASC;
```

Deletion request status overview:

```sql
SELECT
  status,
  count(*) AS total,
  min(requested_at) AS oldest_request,
  max(requested_at) AS newest_request
FROM deletion_requests
GROUP BY status
ORDER BY status;
```

Retention policy overview with estimated action dates:

```sql
SELECT
  entity_type,
  retention_days,
  action,
  is_active,
  retention_days || ' days' AS retention_period
FROM retention_policies
WHERE is_active = true
ORDER BY entity_type;
```

Consent audit trail for a specific entity:

```sql
SELECT
  cr.purpose,
  cr.legal_basis,
  cr.granted_at,
  cr.revoked_at,
  cr.expires_at,
  cr.ip_address,
  cr.source,
  CASE
    WHEN cr.revoked_at IS NOT NULL THEN 'revoked'
    WHEN cr.expires_at IS NOT NULL AND cr.expires_at < now() THEN 'expired'
    ELSE 'active'
  END AS consent_status
FROM consent_records cr
WHERE cr.entity_type = 'contact'
  AND cr.entity_id = '<contact_id>'
ORDER BY cr.granted_at DESC;
```

Pending deletion requests older than 30 days:

```sql
SELECT
  id,
  requester_type,
  requester_id,
  reason,
  requested_at,
  notes
FROM deletion_requests
WHERE status = 'requested'
  AND requested_at < now() - interval '30 days'
ORDER BY requested_at ASC;
```
