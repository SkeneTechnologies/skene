-- Support seed data: 5 tickets with various statuses, priorities, channels
-- Depends on: identity/seed.sql, crm/seed.sql
BEGIN;

INSERT INTO public.tickets (id, org_id, contact_id, assignee_id, creator_id, title, description, status, priority, channel, created_at) VALUES
  ('a6000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'f2000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000005', 'b0000000-0000-0000-0000-000000000005', 'Cannot export CSV reports',       'Export button returns 500 error on large datasets',  'open',     'high',   'email', now() - interval '2 days'),
  ('a6000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'f2000000-0000-0000-0000-000000000007', 'b0000000-0000-0000-0000-000000000005', 'b0000000-0000-0000-0000-000000000005', 'SSO configuration not working',   'SAML assertion failing with IdP timeout',            'pending',  'high',   'chat',  now() - interval '5 days'),
  ('a6000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'f2000000-0000-0000-0000-000000000008', 'b0000000-0000-0000-0000-000000000005', 'b0000000-0000-0000-0000-000000000005', 'Billing invoice formatting',      'Tax line items not showing on PDF invoices',         'resolved', 'medium', 'email', now() - interval '15 days'),
  ('a6000000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000001', 'f2000000-0000-0000-0000-000000000013', 'b0000000-0000-0000-0000-000000000004', 'b0000000-0000-0000-0000-000000000005', 'API rate limiting too aggressive', 'Getting 429s at 50 req/min, expected limit is 100',  'open',     'medium', 'email', now() - interval '1 day'),
  ('a6000000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-000000000001', 'f2000000-0000-0000-0000-000000000003', 'b0000000-0000-0000-0000-000000000005', 'b0000000-0000-0000-0000-000000000005', 'Feature request: dark mode',      'Multiple users requesting dark mode support',        'closed',   'low',    'chat',  now() - interval '30 days');

COMMIT;
