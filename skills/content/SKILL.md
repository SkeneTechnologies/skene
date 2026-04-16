---
name: content
description: Folders, documents, and polymorphic threaded comments for wikis, notes, and knowledge bases.
---

# Content

Hierarchical folders, documents, and threaded comments. Documents live in folders (or at the root) and move through draft, published, and archived statuses. Comments are polymorphic and can attach to documents, tasks, tickets, deals, projects, contacts, or companies.

## Tables

### folders

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| parent_id | uuid | Self-referencing FK. NULL for root folders. Cascade delete. |
| name | text | Folder name. |
| description | text | Optional description. |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

### documents

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| folder_id | uuid | References folders. Set NULL on folder delete. |
| author_id | uuid | References users. Set NULL on user delete. |
| title | text | Document title. |
| body | text | Document content. |
| status | document_status | One of: draft, published, archived. Defaults to draft. |
| published_at | timestamptz | Timestamp when document was published. |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

### comments

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| author_id | uuid | References users. Set NULL on user delete. |
| entity_type | text | Type of parent record. Constrained to: task, ticket, document, deal, project, contact, company. |
| entity_id | uuid | ID of the parent record. |
| body | text | Comment text. |
| parent_id | uuid | Self-referencing FK for threaded replies. Cascade delete. |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

## Enums

### document_status

| Value | Description |
|-------|-------------|
| draft | Document is a work in progress. |
| published | Document is visible to the organization. |
| archived | Document is hidden from default views. |

## Row-Level Security

All three tables are scoped to the current user's organization via `get_user_org_id()`. Any org member can select, insert, and update rows. Only admins (checked via `is_admin()`) can delete folders, documents, or comments.

## Dependencies

- **identity** -- organizations, users, `get_user_org_id()`, `is_admin()`, `set_updated_at()`

## Example Queries

List published documents in a folder, newest first:

```sql
SELECT id, title, author_id, published_at
FROM documents
WHERE folder_id = '<folder_id>'
  AND status = 'published'
ORDER BY published_at DESC;
```

Build the full folder hierarchy for an organization using a recursive CTE:

```sql
WITH RECURSIVE tree AS (
  SELECT id, name, parent_id, 1 AS depth
  FROM folders
  WHERE parent_id IS NULL

  UNION ALL

  SELECT f.id, f.name, f.parent_id, t.depth + 1
  FROM folders f
  JOIN tree t ON t.id = f.parent_id
)
SELECT * FROM tree
ORDER BY depth, name;
```

Fetch all comments (with author) on a specific document, ordered by creation time:

```sql
SELECT
  c.id,
  c.body,
  c.parent_id,
  c.created_at,
  u.full_name AS author_name
FROM comments c
LEFT JOIN users u ON u.id = c.author_id
WHERE c.entity_type = 'document'
  AND c.entity_id = '<document_id>'
ORDER BY c.created_at ASC;
```

Search documents by title or body text:

```sql
SELECT id, title, status, updated_at
FROM documents
WHERE (title ILIKE '%' || '<search_term>' || '%'
       OR body ILIKE '%' || '<search_term>' || '%')
ORDER BY updated_at DESC
LIMIT 20;
```

List the 10 most recently updated documents across all folders:

```sql
SELECT
  d.id,
  d.title,
  d.status,
  d.updated_at,
  f.name AS folder_name
FROM documents d
LEFT JOIN folders f ON f.id = d.folder_id
ORDER BY d.updated_at DESC
LIMIT 10;
```

Count documents per folder, including folders with zero documents:

```sql
SELECT
  f.id,
  f.name,
  count(d.id) AS document_count
FROM folders f
LEFT JOIN documents d ON d.folder_id = f.id
GROUP BY f.id, f.name
ORDER BY document_count DESC;
```
