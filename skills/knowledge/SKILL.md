---
name: knowledge
description: Knowledge base articles organized into hierarchical categories with slug-based URLs and view tracking.
---

# Knowledge

Articles, categories, and many-to-many links between them. Articles move through draft, published, and archived statuses. Categories support nesting via parent_id for multi-level navigation trees. Each article can belong to multiple categories.

## Tables

### articles

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| author_id | uuid | References users. Set NULL on user delete. |
| title | text | Article title. |
| slug | text | URL-friendly identifier, unique per org. |
| body | text | Full article content. |
| excerpt | text | Short summary for listings and search results. |
| status | article_status | One of: draft, published, archived. Defaults to draft. |
| is_featured | boolean | Pinned articles shown prominently. Defaults to false. |
| view_count | integer | Read counter, incremented by the application layer. Defaults to 0. |
| published_at | timestamptz | Timestamp when the article was published. |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

### article_categories

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| name | text | Category display name. |
| slug | text | URL-friendly identifier, unique per org. |
| description | text | Optional category description. |
| parent_id | uuid | Self-referencing FK. NULL for top-level categories. Cascade delete. |
| position | integer | Sort order within the same parent. Defaults to 0. |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

### article_category_links

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| article_id | uuid | References articles. Cascade delete. |
| category_id | uuid | References article_categories. Cascade delete. |
| position | integer | Sort order within the category. Defaults to 0. |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

## Enums

### article_status

| Value | Description |
|-------|-------------|
| draft | Article is a work in progress. |
| published | Article is visible to the organization. |
| archived | Article is hidden from default views. |

## Row-Level Security

All three tables are scoped to the current user's organization via `get_user_org_id()`. Any org member can select, insert, and update rows. Only admins (checked via `is_admin()`) can delete articles, categories, or links.

## Dependencies

- **content** -- folders, documents, comments
- **identity** -- organizations, users, `get_user_org_id()`, `is_admin()`, `set_updated_at()`

## Example Queries

List published articles, newest first:

```sql
SELECT id, title, slug, excerpt, author_id, published_at, view_count
FROM articles
WHERE status = 'published'
ORDER BY published_at DESC;
```

Fetch published articles in a specific category:

```sql
SELECT a.id, a.title, a.slug, a.excerpt, a.published_at
FROM articles a
JOIN article_category_links acl ON acl.article_id = a.id
WHERE acl.category_id = '<category_id>'
  AND a.status = 'published'
ORDER BY acl.position ASC;
```

Search articles by title or body text:

```sql
SELECT id, title, slug, excerpt, status, updated_at
FROM articles
WHERE (title ILIKE '%' || '<search_term>' || '%'
       OR body ILIKE '%' || '<search_term>' || '%')
ORDER BY updated_at DESC
LIMIT 20;
```

List featured articles:

```sql
SELECT id, title, slug, excerpt, view_count, published_at
FROM articles
WHERE is_featured = true
  AND status = 'published'
ORDER BY published_at DESC;
```

Build the full category hierarchy using a recursive CTE:

```sql
WITH RECURSIVE tree AS (
  SELECT id, name, slug, parent_id, position, 1 AS depth
  FROM article_categories
  WHERE parent_id IS NULL

  UNION ALL

  SELECT c.id, c.name, c.slug, c.parent_id, c.position, t.depth + 1
  FROM article_categories c
  JOIN tree t ON t.id = c.parent_id
)
SELECT * FROM tree
ORDER BY depth, position, name;
```

Count articles per category:

```sql
SELECT
  c.id,
  c.name,
  count(acl.article_id) AS article_count
FROM article_categories c
LEFT JOIN article_category_links acl ON acl.category_id = c.id
GROUP BY c.id, c.name
ORDER BY article_count DESC;
```
