---
name: pipeline
description: Sales and recruiting pipelines with stages, deals, and stage transition history
---

# Pipeline

Sales and recruiting pipelines with ordered stages, deals, and an append-only log of stage transitions. Deals track value, status, and expected close date. Stage history enables pipeline velocity analysis.

## Tables

### pipelines

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| org_id | uuid | FK to organizations |
| name | text | Pipeline name (e.g. Sales, Recruiting) |
| description | text | Pipeline description |
| is_default | boolean | Whether this is the default pipeline for the org |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Last update timestamp (auto-set by trigger) |
| metadata | jsonb | Arbitrary JSON |

### pipeline_stages

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| org_id | uuid | FK to organizations |
| pipeline_id | uuid | FK to pipelines |
| name | text | Stage name (e.g. Qualification, Proposal) |
| position | integer | Display order within the pipeline |
| color | text | Hex color for UI rendering |
| is_terminal | boolean | Whether this stage is a final state (e.g. Closed Won, Rejected) |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Last update timestamp (auto-set by trigger) |
| metadata | jsonb | Arbitrary JSON |

Unique constraint on (pipeline_id, position).

### deals

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| org_id | uuid | FK to organizations |
| pipeline_id | uuid | FK to pipelines |
| stage_id | uuid | FK to pipeline_stages. Current stage of the deal |
| owner_id | uuid | FK to users. Deal owner |
| contact_id | uuid | FK to contacts. Associated contact |
| company_id | uuid | FK to companies. Associated company |
| title | text | Deal title |
| value | numeric | Deal value in smallest currency unit (cents) |
| currency | text | Currency code, defaults to USD |
| status | deal_status | Current status: open, won, lost, or stale |
| expected_close_date | date | Forecasted close date |
| closed_at | timestamptz | When the deal was actually closed |
| lost_reason | text | Free-text explanation when status is lost |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Last update timestamp (auto-set by trigger) |
| metadata | jsonb | Arbitrary JSON |

### deal_stage_history

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| org_id | uuid | FK to organizations |
| deal_id | uuid | FK to deals |
| from_stage_id | uuid | FK to pipeline_stages. Stage the deal moved from |
| to_stage_id | uuid | FK to pipeline_stages. Stage the deal moved to |
| changed_by | uuid | FK to users. Who triggered the transition |
| changed_at | timestamptz | When the transition happened |
| duration_seconds | integer | Time spent in the previous stage |
| created_at | timestamptz | Row creation timestamp |
| updated_at | timestamptz | Last update timestamp (auto-set by trigger) |
| metadata | jsonb | Arbitrary JSON |

## Enums

### deal_status

| Value | Description |
|-------|-------------|
| open | Deal is active and in progress |
| won | Deal was closed successfully |
| lost | Deal was lost |
| stale | Deal has gone inactive with no recent updates |

## Row-Level Security

All tables have RLS enabled and are scoped to the current user's organization via `get_user_org_id()`.

- **pipelines**: SELECT/INSERT/UPDATE for own org. DELETE requires admin.
- **pipeline_stages**: SELECT/INSERT/UPDATE for own org. DELETE requires admin.
- **deals**: SELECT/INSERT/UPDATE for own org. DELETE requires admin.
- **deal_stage_history**: SELECT/INSERT/UPDATE for own org. DELETE requires admin.

## Dependencies

- `crm` -- contacts and companies referenced by deals

## Example Queries

Get all deals in a specific stage:

```sql
SELECT
  d.title,
  d.value / 100.0 AS value_dollars,
  d.currency,
  u.full_name AS owner,
  c.first_name || ' ' || coalesce(c.last_name, '') AS contact
FROM deals d
LEFT JOIN users u ON u.id = d.owner_id
LEFT JOIN contacts c ON c.id = d.contact_id
WHERE d.stage_id = '<stage_id>'
  AND d.status = 'open'
ORDER BY d.value DESC;
```

Pipeline summary with deal counts and total value:

```sql
SELECT
  ps.name AS stage,
  ps.position,
  count(d.id) AS deal_count,
  coalesce(sum(d.value), 0) / 100.0 AS total_value
FROM pipeline_stages ps
LEFT JOIN deals d ON d.stage_id = ps.id AND d.status = 'open'
WHERE ps.pipeline_id = '<pipeline_id>'
GROUP BY ps.id, ps.name, ps.position
ORDER BY ps.position;
```

Average time in each stage (pipeline velocity):

```sql
SELECT
  ps.name AS stage,
  round(avg(dsh.duration_seconds) / 86400.0, 1) AS avg_days
FROM deal_stage_history dsh
JOIN pipeline_stages ps ON ps.id = dsh.from_stage_id
WHERE dsh.duration_seconds IS NOT NULL
GROUP BY ps.id, ps.name, ps.position
ORDER BY ps.position;
```

Deals expected to close this month:

```sql
SELECT
  d.title,
  d.value / 100.0 AS value_dollars,
  d.expected_close_date,
  ps.name AS stage,
  u.full_name AS owner
FROM deals d
JOIN pipeline_stages ps ON ps.id = d.stage_id
LEFT JOIN users u ON u.id = d.owner_id
WHERE d.status = 'open'
  AND d.expected_close_date >= date_trunc('month', current_date)
  AND d.expected_close_date < date_trunc('month', current_date) + interval '1 month'
ORDER BY d.expected_close_date;
```

Win/loss breakdown by owner:

```sql
SELECT
  u.full_name AS owner,
  count(*) FILTER (WHERE d.status = 'won') AS won,
  count(*) FILTER (WHERE d.status = 'lost') AS lost,
  round(
    100.0 * count(*) FILTER (WHERE d.status = 'won')
    / nullif(count(*) FILTER (WHERE d.status IN ('won', 'lost')), 0),
    1
  ) AS win_rate_pct
FROM deals d
JOIN users u ON u.id = d.owner_id
WHERE d.org_id = get_user_org_id()
  AND d.status IN ('won', 'lost')
GROUP BY u.id, u.full_name
ORDER BY win_rate_pct DESC;
```
