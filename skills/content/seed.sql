-- Content seed data: engineering docs with comments
BEGIN;

INSERT INTO public.folders (id, org_id, name, description) VALUES
  ('a9000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'Engineering Docs', 'Technical documentation and architecture decisions');

INSERT INTO public.documents (id, org_id, folder_id, author_id, title, body, status, published_at) VALUES
  ('aa000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'a9000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000003', 'Platform v2 Architecture', 'Overview of the v2 platform architecture, including service boundaries, data flow, and deployment topology.', 'published', now() - interval '60 days'),
  ('aa000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'a9000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000004', 'API Authentication Guide', 'Guide for implementing JWT-based auth with role-based access control in the v2 API.', 'draft', NULL);

INSERT INTO public.comments (org_id, author_id, entity_type, entity_id, body) VALUES
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000004', 'document', 'aa000000-0000-0000-0000-000000000001', 'Should we add a section on the caching strategy? The Redis layer is a big part of v2.'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000003', 'document', 'aa000000-0000-0000-0000-000000000001', 'Good call. I will add a caching section this week.'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000005', 'task',     'a5000000-0000-0000-0000-000000000003', 'The v1 to v2 migration script needs to handle the edge case where contacts have duplicate emails across orgs.');

COMMIT;
