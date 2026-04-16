---
name: approvals
description: Multi-step approval chains with requests, decisions, and temporary delegations.
---

# Approvals

Configurable approval workflows for any entity type. A chain defines the sequence of steps. Each step names either a specific approver or a role. Requests track the overall status of an approval, while decisions record each individual approve or reject action. Delegations allow temporary hand-off of approval authority.

## Tables

### approval_chains

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| name | text | Chain display name. |
| description | text | Optional description of the workflow. |
| entity_type | text | The kind of record this chain applies to (e.g. expense, contract). |
| is_active | boolean | Inactive chains are not used for new requests. Defaults to true. |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

### approval_steps

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| chain_id | uuid | References approval_chains. Cascade delete. |
| position | integer | Execution order within the chain. Lower values run first. |
| approver_id | uuid | References users. Set NULL on user delete. NULL when using role-based approval. |
| approver_role | text | Role name for role-based approval. Used when approver_id is NULL. |
| is_required | boolean | If false, this step may be skipped. Defaults to true. |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

### approval_requests

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| chain_id | uuid | References approval_chains. Cascade delete. |
| entity_type | text | The kind of record being approved. |
| entity_id | uuid | The ID of the record being approved. |
| requester_id | uuid | References users. Set NULL on user delete. |
| status | approval_status | One of: pending, approved, rejected, canceled. Defaults to pending. |
| submitted_at | timestamptz | When the request was submitted. Defaults to now. |
| resolved_at | timestamptz | When the request reached a terminal status. |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

### approval_decisions

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| request_id | uuid | References approval_requests. Cascade delete. |
| step_id | uuid | References approval_steps. Set NULL on step delete. |
| decided_by | uuid | References users. Set NULL on user delete. |
| decision | approval_decision | One of: approved, rejected. |
| comment | text | Optional note explaining the decision. |
| decided_at | timestamptz | When the decision was made. Defaults to now. |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

### approval_delegations

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| delegator_id | uuid | References users. Cascade delete. |
| delegate_id | uuid | References users. Cascade delete. |
| chain_id | uuid | References approval_chains. Set NULL on chain delete. NULL means all chains. |
| starts_at | timestamptz | When the delegation begins. Defaults to now. |
| ends_at | timestamptz | When the delegation expires. NULL means no expiration. |
| reason | text | Optional explanation for the delegation. |
| is_active | boolean | Whether the delegation is currently in effect. Defaults to true. |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

## Enums

### approval_status

| Value | Description |
|-------|-------------|
| pending | Request is awaiting decisions. |
| approved | All required steps have been approved. |
| rejected | At least one required step was rejected. |
| canceled | Requester withdrew the request. |

### approval_decision

| Value | Description |
|-------|-------------|
| approved | The approver accepted the request at this step. |
| rejected | The approver declined the request at this step. |

## Row-Level Security

All five tables are scoped to the current user's organization via `get_user_org_id()`. Any org member can select, insert, and update rows. Only admins (checked via `is_admin()`) can delete chains, steps, requests, decisions, or delegations.

## Dependencies

- **identity** -- organizations, users, `get_user_org_id()`, `is_admin()`, `set_updated_at()`

## Example Queries

List pending approval requests assigned to the current user (via steps or delegation):

```sql
SELECT
  ar.id,
  ar.entity_type,
  ar.entity_id,
  ar.submitted_at,
  u.full_name AS requester_name
FROM approval_requests ar
JOIN approval_chains ac ON ac.id = ar.chain_id
JOIN approval_steps ast ON ast.chain_id = ac.id
LEFT JOIN users u ON u.id = ar.requester_id
WHERE ar.status = 'pending'
  AND ast.approver_id = '<current_user_id>'
ORDER BY ar.submitted_at ASC;
```

Full decision history for a specific request:

```sql
SELECT
  ad.decision,
  ad.comment,
  ad.decided_at,
  u.full_name AS decided_by_name,
  ast.position AS step_position
FROM approval_decisions ad
LEFT JOIN users u ON u.id = ad.decided_by
LEFT JOIN approval_steps ast ON ast.id = ad.step_id
WHERE ad.request_id = '<request_id>'
ORDER BY ad.decided_at ASC;
```

Active delegations for a user:

```sql
SELECT
  d.id,
  d.delegator_id,
  u_from.full_name AS delegator_name,
  u_to.full_name   AS delegate_name,
  ac.name           AS chain_name,
  d.starts_at,
  d.ends_at,
  d.reason
FROM approval_delegations d
LEFT JOIN users u_from ON u_from.id = d.delegator_id
LEFT JOIN users u_to   ON u_to.id   = d.delegate_id
LEFT JOIN approval_chains ac ON ac.id = d.chain_id
WHERE d.is_active = true
  AND d.starts_at <= now()
  AND (d.ends_at IS NULL OR d.ends_at > now())
ORDER BY d.starts_at DESC;
```

Approval chain with all steps, ordered by position:

```sql
SELECT
  ac.name AS chain_name,
  ast.position,
  COALESCE(u.full_name, ast.approver_role) AS approver,
  ast.is_required
FROM approval_chains ac
JOIN approval_steps ast ON ast.chain_id = ac.id
LEFT JOIN users u ON u.id = ast.approver_id
WHERE ac.id = '<chain_id>'
ORDER BY ast.position ASC;
```

Summary of request counts by status for each chain:

```sql
SELECT
  ac.name AS chain_name,
  ar.status,
  count(*) AS request_count
FROM approval_requests ar
JOIN approval_chains ac ON ac.id = ar.chain_id
GROUP BY ac.name, ar.status
ORDER BY ac.name, ar.status;
```

Requests resolved in the last 30 days with time-to-resolution:

```sql
SELECT
  ar.id,
  ar.entity_type,
  ar.status,
  ar.submitted_at,
  ar.resolved_at,
  ar.resolved_at - ar.submitted_at AS resolution_time
FROM approval_requests ar
WHERE ar.resolved_at >= now() - interval '30 days'
ORDER BY ar.resolved_at DESC;
```
