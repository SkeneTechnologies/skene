---
name: tasks
description: Projects, tasks, and task dependencies for tracking work
---

# Tasks

Projects, tasks, and blocking dependencies for organizing and tracking work items across an organization.

## Tables

### projects

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated |
| org_id | uuid | References organizations. CASCADE on delete |
| owner_id | uuid | References users. SET NULL on delete |
| name | text | Project name (required) |
| description | text | Optional project description |
| status | task_status | Current status, defaults to 'todo' |
| priority | task_priority | Priority level, defaults to 'medium' |
| starts_at | date | Planned start date |
| due_at | date | Target completion date |
| completed_at | timestamptz | When the project was completed |
| created_at | timestamptz | Row creation time |
| updated_at | timestamptz | Auto-updated on change via trigger |
| metadata | jsonb | Freeform JSON, defaults to empty object |

### tasks

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated |
| org_id | uuid | References organizations. CASCADE on delete |
| project_id | uuid | References projects. CASCADE on delete. Optional |
| assignee_id | uuid | References users. SET NULL on delete |
| creator_id | uuid | References users. SET NULL on delete |
| title | text | Task title (required) |
| description | text | Optional task description |
| status | task_status | Current status, defaults to 'todo' |
| priority | task_priority | Priority level, defaults to 'medium' |
| due_at | date | Target completion date |
| completed_at | timestamptz | When the task was completed |
| position | integer | Sort order within project, defaults to 0 |
| created_at | timestamptz | Row creation time |
| updated_at | timestamptz | Auto-updated on change via trigger |
| metadata | jsonb | Freeform JSON, defaults to empty object |

### task_dependencies

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated |
| org_id | uuid | References organizations. CASCADE on delete |
| task_id | uuid | The blocked task. References tasks. CASCADE on delete |
| depends_on_id | uuid | The blocking task. References tasks. CASCADE on delete |
| created_at | timestamptz | Row creation time |
| updated_at | timestamptz | Auto-updated on change via trigger |
| metadata | jsonb | Freeform JSON, defaults to empty object |

Constraints: (task_id, depends_on_id) is unique, and a task cannot depend on itself.

## Enums

### task_status

| Value | Description |
|-------|-------------|
| todo | Not yet started |
| in_progress | Work is underway |
| in_review | Waiting for review |
| done | Completed |
| cancelled | Cancelled, will not be done |

### task_priority

| Value | Description |
|-------|-------------|
| low | Low priority |
| medium | Medium priority (default) |
| high | High priority |
| urgent | Needs immediate attention |

## Row-Level Security

All three tables have RLS enabled and scoped to org_id via `get_user_org_id()`. SELECT, INSERT, and UPDATE are open to all org members. DELETE requires admin privileges via `is_admin()`.

## Dependencies

- identity (organizations, users)

## Example Queries

```sql
-- Overdue tasks for a user
SELECT
  t.title,
  t.priority,
  t.due_at,
  p.name AS project
FROM tasks t
LEFT JOIN projects p ON p.id = t.project_id
WHERE t.assignee_id = '<user_id>'
  AND t.status NOT IN ('done', 'cancelled')
  AND t.due_at < current_date
ORDER BY t.due_at ASC;
```

```sql
-- Project progress summary
SELECT
  p.name,
  count(*) FILTER (WHERE t.status = 'done') AS completed,
  count(*) FILTER (WHERE t.status NOT IN ('done', 'cancelled')) AS remaining,
  round(
    100.0 * count(*) FILTER (WHERE t.status = 'done') / nullif(count(*), 0),
    0
  ) AS percent_complete
FROM projects p
JOIN tasks t ON t.project_id = p.id
GROUP BY p.id, p.name;
```

```sql
-- Tasks blocked by incomplete dependencies
SELECT
  t.title AS blocked_task,
  dep.title AS blocking_task,
  dep.status AS blocking_status
FROM task_dependencies td
JOIN tasks t ON t.id = td.task_id
JOIN tasks dep ON dep.id = td.depends_on_id
WHERE dep.status NOT IN ('done', 'cancelled')
ORDER BY t.title;
```

```sql
-- Workload per assignee across active projects
SELECT
  u.full_name,
  count(*) FILTER (WHERE t.priority = 'urgent') AS urgent,
  count(*) FILTER (WHERE t.priority = 'high') AS high,
  count(*) FILTER (WHERE t.priority = 'medium') AS medium,
  count(*) FILTER (WHERE t.priority = 'low') AS low,
  count(*) AS total
FROM tasks t
JOIN users u ON u.id = t.assignee_id
WHERE t.status NOT IN ('done', 'cancelled')
GROUP BY u.id, u.full_name
ORDER BY count(*) FILTER (WHERE t.priority = 'urgent') DESC, total DESC;
```

```sql
-- Recently completed tasks with time to completion
SELECT
  t.title,
  t.priority,
  p.name AS project,
  t.completed_at,
  extract(epoch FROM t.completed_at - t.created_at) / 86400 AS days_to_complete
FROM tasks t
LEFT JOIN projects p ON p.id = t.project_id
WHERE t.status = 'done'
  AND t.completed_at >= now() - interval '7 days'
ORDER BY t.completed_at DESC;
```
