-- Compliance seed data: consent records, deletion requests, and retention policies
BEGIN;

INSERT INTO public.consent_records (id, org_id, entity_type, entity_id, purpose, legal_basis, granted_at, revoked_at, expires_at, ip_address, source) VALUES
  ('c9000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'contact', 'f2000000-0000-0000-0000-000000000001', 'marketing_email', 'consent', now() - interval '180 days', NULL, now() + interval '365 days', '192.168.1.10', 'signup_form'),
  ('c9000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'contact', 'f2000000-0000-0000-0000-000000000001', 'analytics',       'legitimate_interest', now() - interval '180 days', NULL, NULL, '192.168.1.10', 'signup_form'),
  ('c9000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'contact', 'f2000000-0000-0000-0000-000000000002', 'marketing_email', 'consent', now() - interval '120 days', now() - interval '30 days', NULL, '10.0.0.5', 'web_form'),
  ('c9000000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000001', 'contact', 'f2000000-0000-0000-0000-000000000003', 'marketing_email', 'consent', now() - interval '90 days', NULL, now() + interval '275 days', '172.16.0.20', 'signup_form'),
  ('c9000000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-000000000001', 'contact', 'f2000000-0000-0000-0000-000000000003', 'analytics',       'legitimate_interest', now() - interval '90 days', NULL, NULL, '172.16.0.20', 'signup_form'),
  ('c9000000-0000-0000-0000-000000000006', 'a0000000-0000-0000-0000-000000000001', 'contact', 'f2000000-0000-0000-0000-000000000004', 'marketing_email', 'consent', now() - interval '400 days', NULL, now() - interval '35 days', '10.0.0.15', 'import');

INSERT INTO public.deletion_requests (id, org_id, requester_type, requester_id, status, reason, requested_at, completed_at, completed_by, notes) VALUES
  ('c9000000-0000-0000-0000-000000000010', 'a0000000-0000-0000-0000-000000000001', 'contact', 'f2000000-0000-0000-0000-000000000002', 'requested', 'GDPR right to erasure -- customer requested via email', now() - interval '5 days', NULL, NULL, 'Pending review by compliance team');

INSERT INTO public.retention_policies (id, org_id, entity_type, retention_days, action, is_active) VALUES
  ('c9000000-0000-0000-0000-000000000020', 'a0000000-0000-0000-0000-000000000001', 'contacts',      730,  'anonymize', true),
  ('c9000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000001', 'support_tickets', 365, 'archive',   true),
  ('c9000000-0000-0000-0000-000000000022', 'a0000000-0000-0000-0000-000000000001', 'audit_logs',    1095, 'delete',    true),
  ('c9000000-0000-0000-0000-000000000023', 'a0000000-0000-0000-0000-000000000001', 'sync_logs',      180, 'delete',    true);

COMMIT;
