-- Integrations seed data: connected apps, OAuth tokens, webhooks, events, and sync logs
BEGIN;

INSERT INTO public.connected_apps (id, org_id, name, provider, status, config, connected_by, connected_at) VALUES
  ('c8000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'Slack',   'slack',   'active', '{"channel": "#general", "bot_token": true}', 'b0000000-0000-0000-0000-000000000001', now() - interval '90 days'),
  ('c8000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'HubSpot', 'hubspot', 'active', '{"portal_id": "12345", "sync_contacts": true}', 'b0000000-0000-0000-0000-000000000001', now() - interval '60 days'),
  ('c8000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'Stripe',  'stripe',  'active', '{"account_id": "acct_abc123", "mode": "live"}', 'b0000000-0000-0000-0000-000000000003', now() - interval '30 days');

INSERT INTO public.oauth_tokens (id, org_id, app_id, user_id, access_token_enc, refresh_token_enc, token_type, scopes, expires_at) VALUES
  ('c8000000-0000-0000-0000-000000000010', 'a0000000-0000-0000-0000-000000000001', 'c8000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'enc:xoxb-slack-token-user1', 'enc:xoxr-slack-refresh-user1', 'bearer', ARRAY['chat:write','channels:read'], now() + interval '30 days'),
  ('c8000000-0000-0000-0000-000000000011', 'a0000000-0000-0000-0000-000000000001', 'c8000000-0000-0000-0000-000000000002', 'b0000000-0000-0000-0000-000000000001', 'enc:hubspot-token-user1', 'enc:hubspot-refresh-user1', 'bearer', ARRAY['contacts','deals'], now() + interval '60 days'),
  ('c8000000-0000-0000-0000-000000000012', 'a0000000-0000-0000-0000-000000000001', 'c8000000-0000-0000-0000-000000000002', 'b0000000-0000-0000-0000-000000000003', 'enc:hubspot-token-user3', NULL, 'bearer', ARRAY['contacts'], now() + interval '60 days');

INSERT INTO public.webhooks (id, org_id, url, secret, events, is_active, created_by) VALUES
  ('c8000000-0000-0000-0000-000000000020', 'a0000000-0000-0000-0000-000000000001', 'https://hooks.example.com/contact-created', 'whsec_abc123', ARRAY['contact.created'], true, 'b0000000-0000-0000-0000-000000000001'),
  ('c8000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000001', 'https://hooks.example.com/deal-closed',    'whsec_def456', ARRAY['deal.closed_won','deal.closed_lost'], true, 'b0000000-0000-0000-0000-000000000001'),
  ('c8000000-0000-0000-0000-000000000022', 'a0000000-0000-0000-0000-000000000001', 'https://hooks.example.com/ticket-updated',  'whsec_ghi789', ARRAY['ticket.updated','ticket.resolved'], true, 'b0000000-0000-0000-0000-000000000003'),
  ('c8000000-0000-0000-0000-000000000023', 'a0000000-0000-0000-0000-000000000001', 'https://hooks.example.com/invoice-paid',    'whsec_jkl012', ARRAY['invoice.paid'], true, 'b0000000-0000-0000-0000-000000000001'),
  ('c8000000-0000-0000-0000-000000000024', 'a0000000-0000-0000-0000-000000000001', 'https://hooks.example.com/old-endpoint',    'whsec_mno345', ARRAY['contact.updated'], false, 'b0000000-0000-0000-0000-000000000001');

INSERT INTO public.webhook_events (id, org_id, webhook_id, event_type, payload, status, response_code, attempts, last_attempt_at) VALUES
  ('c8000000-0000-0000-0000-000000000030', 'a0000000-0000-0000-0000-000000000001', 'c8000000-0000-0000-0000-000000000020', 'contact.created', '{"contact_id": "f2000000-0000-0000-0000-000000000001", "email": "alice@example.com"}', 'sent', 200, 1, now() - interval '2 days'),
  ('c8000000-0000-0000-0000-000000000031', 'a0000000-0000-0000-0000-000000000001', 'c8000000-0000-0000-0000-000000000021', 'deal.closed_won', '{"deal_id": "d0000001", "amount": 15000}', 'sent', 200, 1, now() - interval '1 day'),
  ('c8000000-0000-0000-0000-000000000032', 'a0000000-0000-0000-0000-000000000001', 'c8000000-0000-0000-0000-000000000022', 'ticket.updated', '{"ticket_id": "t0000001", "status": "in_progress"}', 'failed', 500, 3, now() - interval '6 hours'),
  ('c8000000-0000-0000-0000-000000000033', 'a0000000-0000-0000-0000-000000000001', 'c8000000-0000-0000-0000-000000000020', 'contact.created', '{"contact_id": "f2000000-0000-0000-0000-000000000003", "email": "carol@example.com"}', 'pending', NULL, 0, NULL);

INSERT INTO public.sync_logs (id, org_id, app_id, direction, entity_type, entity_id, status, records_processed, records_failed, started_at, completed_at, error) VALUES
  ('c8000000-0000-0000-0000-000000000040', 'a0000000-0000-0000-0000-000000000001', 'c8000000-0000-0000-0000-000000000002', 'inbound',  'contacts', NULL, 'completed', 142, 0, now() - interval '3 days', now() - interval '3 days' + interval '45 seconds', NULL),
  ('c8000000-0000-0000-0000-000000000041', 'a0000000-0000-0000-0000-000000000001', 'c8000000-0000-0000-0000-000000000002', 'outbound', 'deals',    NULL, 'completed', 28,  2, now() - interval '2 days', now() - interval '2 days' + interval '12 seconds', NULL),
  ('c8000000-0000-0000-0000-000000000042', 'a0000000-0000-0000-0000-000000000001', 'c8000000-0000-0000-0000-000000000003', 'inbound',  'invoices', NULL, 'failed',    0,   0, now() - interval '1 day', now() - interval '1 day' + interval '3 seconds', 'API rate limit exceeded'),
  ('c8000000-0000-0000-0000-000000000043', 'a0000000-0000-0000-0000-000000000001', 'c8000000-0000-0000-0000-000000000001', 'inbound',  'messages', NULL, 'running',   57,  0, now() - interval '10 minutes', NULL, NULL);

COMMIT;
