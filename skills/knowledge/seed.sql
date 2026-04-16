-- Knowledge seed data: articles across three categories
BEGIN;

-- Categories
INSERT INTO public.article_categories (id, org_id, name, slug, description, parent_id, position) VALUES
  ('c6000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'Getting Started',   'getting-started',   'Onboarding guides and first steps.',        NULL, 0),
  ('c6000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'API Reference',     'api-reference',     'Endpoint documentation and usage examples.', NULL, 1),
  ('c6000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'Best Practices',    'best-practices',    'Recommended patterns and conventions.',       NULL, 2);

-- Articles
INSERT INTO public.articles (id, org_id, author_id, title, slug, body, excerpt, status, is_featured, view_count, published_at) VALUES
  ('c6000000-0000-0000-0000-000000000010', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000003', 'Quick Start Guide',          'quick-start-guide',          'Step-by-step instructions for setting up your workspace and creating your first project.',                'Set up your workspace in under five minutes.',       'published', true,  142, now() - interval '45 days'),
  ('c6000000-0000-0000-0000-000000000011', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000004', 'Authentication Overview',    'authentication-overview',    'How authentication works, including JWT tokens, refresh flows, and role-based access control.',           'Understand the auth model from tokens to roles.',    'published', false, 87,  now() - interval '40 days'),
  ('c6000000-0000-0000-0000-000000000012', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000005', 'REST API Endpoints',         'rest-api-endpoints',         'Full reference for all REST endpoints, including request formats, response schemas, and error codes.',    'Complete endpoint listing with examples.',            'published', false, 210, now() - interval '30 days'),
  ('c6000000-0000-0000-0000-000000000013', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000003', 'Webhooks Integration',       'webhooks-integration',       'How to configure outgoing webhooks, verify signatures, and handle retries.',                              'Connect external services via webhooks.',             'published', false, 55,  now() - interval '25 days'),
  ('c6000000-0000-0000-0000-000000000014', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000004', 'Error Handling Patterns',    'error-handling-patterns',    'Recommended strategies for error handling in client and server code, including retry logic and fallback.', 'Robust error handling for production systems.',       'published', true,  96,  now() - interval '20 days'),
  ('c6000000-0000-0000-0000-000000000015', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000005', 'Database Naming Conventions','database-naming-conventions','Standards for table names, column names, indexes, and constraints used across the platform.',             'Consistent naming rules for schema objects.',         'draft',     false, 0,   NULL),
  ('c6000000-0000-0000-0000-000000000016', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000003', 'Rate Limiting',              'rate-limiting',              'How rate limits are enforced, current thresholds, and best practices for staying within limits.',         'Understand and work within API rate limits.',         'published', false, 38,  now() - interval '10 days'),
  ('c6000000-0000-0000-0000-000000000017', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000004', 'Migration Guide v1 to v2',   'migration-guide-v1-to-v2',   'Step-by-step migration path from the v1 API to v2, including breaking changes and compatibility notes.',  'Migrate from v1 to v2 without downtime.',             'draft',     false, 0,   NULL);

-- Category links
INSERT INTO public.article_category_links (id, org_id, article_id, category_id, position) VALUES
  ('c6000000-0000-0000-0000-000000000020', 'a0000000-0000-0000-0000-000000000001', 'c6000000-0000-0000-0000-000000000010', 'c6000000-0000-0000-0000-000000000001', 0),
  ('c6000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000001', 'c6000000-0000-0000-0000-000000000011', 'c6000000-0000-0000-0000-000000000001', 1),
  ('c6000000-0000-0000-0000-000000000022', 'a0000000-0000-0000-0000-000000000001', 'c6000000-0000-0000-0000-000000000012', 'c6000000-0000-0000-0000-000000000002', 0),
  ('c6000000-0000-0000-0000-000000000023', 'a0000000-0000-0000-0000-000000000001', 'c6000000-0000-0000-0000-000000000013', 'c6000000-0000-0000-0000-000000000002', 1),
  ('c6000000-0000-0000-0000-000000000024', 'a0000000-0000-0000-0000-000000000001', 'c6000000-0000-0000-0000-000000000016', 'c6000000-0000-0000-0000-000000000002', 2),
  ('c6000000-0000-0000-0000-000000000025', 'a0000000-0000-0000-0000-000000000001', 'c6000000-0000-0000-0000-000000000014', 'c6000000-0000-0000-0000-000000000003', 0),
  ('c6000000-0000-0000-0000-000000000026', 'a0000000-0000-0000-0000-000000000001', 'c6000000-0000-0000-0000-000000000015', 'c6000000-0000-0000-0000-000000000003', 1),
  ('c6000000-0000-0000-0000-000000000027', 'a0000000-0000-0000-0000-000000000001', 'c6000000-0000-0000-0000-000000000017', 'c6000000-0000-0000-0000-000000000001', 2);

COMMIT;
