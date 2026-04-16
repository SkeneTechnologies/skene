-- Notifications seed data: 5 templates, 20 deliveries, preferences for 5 users, 3 push tokens
BEGIN;

-- Notification templates ----------------------------------------------------------

INSERT INTO public.notification_templates (id, org_id, name, slug, channel, subject, body_template) VALUES
  ('c3000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'Welcome Email',           'welcome-email',        'email',  'Welcome to {{org_name}}',        'Hi {{name}}, your account at {{org_name}} is ready. Log in at {{login_url}} to get started.'),
  ('c3000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'Password Reset',          'password-reset',        'email',  'Reset your password',            'Hi {{name}}, click the link below to reset your password: {{reset_url}}. This link expires in 1 hour.'),
  ('c3000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'New Assignment Push',     'new-assignment-push',   'push',   null,                             '{{assigner}} assigned you to "{{task_name}}".'),
  ('c3000000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000001', 'Invoice Ready',           'invoice-ready',         'email',  'Your invoice is ready',          'Hi {{name}}, invoice #{{invoice_number}} for {{amount}} is available. View it at {{invoice_url}}.'),
  ('c3000000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-000000000001', 'Mention In-App',          'mention-in-app',        'in_app', null,                             '{{mentioner}} mentioned you in {{context}}: "{{snippet}}"');

-- Notification deliveries (20) ---------------------------------------------------

INSERT INTO public.notification_deliveries (id, org_id, template_id, user_id, channel, subject, body, status, sent_at, read_at) VALUES
  -- Welcome emails (5 -- one per user, all delivered)
  ('c3100000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'email', 'Welcome to Acme Corp', 'Hi Sarah, your account at Acme Corp is ready. Log in at https://app.acme.io to get started.', 'delivered', '2025-01-15 09:00:00+00', '2025-01-15 09:05:00+00'),
  ('c3100000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000002', 'email', 'Welcome to Acme Corp', 'Hi Marcus, your account at Acme Corp is ready. Log in at https://app.acme.io to get started.', 'delivered', '2025-01-16 10:00:00+00', '2025-01-16 11:30:00+00'),
  ('c3100000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000003', 'email', 'Welcome to Acme Corp', 'Hi Priya, your account at Acme Corp is ready. Log in at https://app.acme.io to get started.', 'delivered', '2025-01-17 08:30:00+00', '2025-01-17 09:00:00+00'),
  ('c3100000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000004', 'email', 'Welcome to Acme Corp', 'Hi James, your account at Acme Corp is ready. Log in at https://app.acme.io to get started.', 'delivered', '2025-01-18 14:00:00+00', null),
  ('c3100000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000005', 'email', 'Welcome to Acme Corp', 'Hi Elena, your account at Acme Corp is ready. Log in at https://app.acme.io to get started.', 'delivered', '2025-01-19 11:00:00+00', '2025-01-19 12:15:00+00'),

  -- Password reset (2)
  ('c3100000-0000-0000-0000-000000000006', 'a0000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000002', 'b0000000-0000-0000-0000-000000000002', 'email', 'Reset your password', 'Hi Marcus, click the link below to reset your password: https://app.acme.io/reset/abc123. This link expires in 1 hour.', 'delivered', '2025-02-10 15:00:00+00', '2025-02-10 15:02:00+00'),
  ('c3100000-0000-0000-0000-000000000007', 'a0000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000002', 'b0000000-0000-0000-0000-000000000005', 'email', 'Reset your password', 'Hi Elena, click the link below to reset your password: https://app.acme.io/reset/def456. This link expires in 1 hour.', 'sent', '2025-03-01 09:30:00+00', null),

  -- Push notifications (5)
  ('c3100000-0000-0000-0000-000000000008', 'a0000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000003', 'b0000000-0000-0000-0000-000000000003', 'push', null, 'Sarah assigned you to "Q2 roadmap review".', 'delivered', '2025-03-05 10:00:00+00', null),
  ('c3100000-0000-0000-0000-000000000009', 'a0000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000003', 'b0000000-0000-0000-0000-000000000004', 'push', null, 'Priya assigned you to "Fix login bug".', 'delivered', '2025-03-06 14:00:00+00', null),
  ('c3100000-0000-0000-0000-000000000010', 'a0000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000003', 'b0000000-0000-0000-0000-000000000001', 'push', null, 'Marcus assigned you to "Sales forecast March".', 'failed', null, null),
  ('c3100000-0000-0000-0000-000000000011', 'a0000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000003', 'b0000000-0000-0000-0000-000000000002', 'push', null, 'Sarah assigned you to "Update pricing page".', 'delivered', '2025-03-08 09:00:00+00', null),
  ('c3100000-0000-0000-0000-000000000012', 'a0000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000003', 'b0000000-0000-0000-0000-000000000005', 'push', null, 'James assigned you to "Customer escalation #42".', 'queued', null, null),

  -- Invoice emails (3)
  ('c3100000-0000-0000-0000-000000000013', 'a0000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000004', 'b0000000-0000-0000-0000-000000000001', 'email', 'Your invoice is ready', 'Hi Sarah, invoice #INV-2025-001 for $4,500.00 is available. View it at https://app.acme.io/invoices/001.', 'delivered', '2025-03-01 08:00:00+00', '2025-03-01 08:45:00+00'),
  ('c3100000-0000-0000-0000-000000000014', 'a0000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000004', 'b0000000-0000-0000-0000-000000000001', 'email', 'Your invoice is ready', 'Hi Sarah, invoice #INV-2025-002 for $4,500.00 is available. View it at https://app.acme.io/invoices/002.', 'sent', '2025-04-01 08:00:00+00', null),
  ('c3100000-0000-0000-0000-000000000015', 'a0000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000004', 'b0000000-0000-0000-0000-000000000001', 'email', 'Your invoice is ready', 'Hi Sarah, invoice #INV-2025-003 for $4,500.00 is available. View it at https://app.acme.io/invoices/003.', 'queued', null, null),

  -- In-app mentions (5)
  ('c3100000-0000-0000-0000-000000000016', 'a0000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000005', 'b0000000-0000-0000-0000-000000000001', 'in_app', null, 'Marcus mentioned you in #sales: "thoughts on this lead?"', 'read', '2025-03-10 10:00:00+00', '2025-03-10 10:05:00+00'),
  ('c3100000-0000-0000-0000-000000000017', 'a0000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000005', 'b0000000-0000-0000-0000-000000000002', 'in_app', null, 'Sarah mentioned you in #sales: "can you follow up?"', 'delivered', '2025-03-10 11:00:00+00', null),
  ('c3100000-0000-0000-0000-000000000018', 'a0000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000005', 'b0000000-0000-0000-0000-000000000003', 'in_app', null, 'James mentioned you in #engineering: "please review PR #87"', 'delivered', '2025-03-11 09:00:00+00', null),
  ('c3100000-0000-0000-0000-000000000019', 'a0000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000005', 'b0000000-0000-0000-0000-000000000004', 'in_app', null, 'Priya mentioned you in #engineering: "deploy is ready"', 'read', '2025-03-12 16:00:00+00', '2025-03-12 16:10:00+00'),
  ('c3100000-0000-0000-0000-000000000020', 'a0000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000005', 'b0000000-0000-0000-0000-000000000005', 'in_app', null, 'Sarah mentioned you in #support: "escalation resolved"', 'queued', null, null);

-- Update the failed delivery with an error message
UPDATE public.notification_deliveries
SET error = 'push token expired'
WHERE id = 'c3100000-0000-0000-0000-000000000010';

-- Notification preferences (5 users x 4 channels = 20 rows) ----------------------

INSERT INTO public.notification_preferences (id, org_id, user_id, channel, category, is_enabled) VALUES
  -- Sarah (all enabled)
  ('c3200000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'email',  'general',   true),
  ('c3200000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'push',   'general',   true),
  ('c3200000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'in_app', 'general',   true),
  ('c3200000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'sms',    'general',   false),
  -- Marcus (push disabled)
  ('c3200000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000002', 'email',  'general',   true),
  ('c3200000-0000-0000-0000-000000000006', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000002', 'push',   'general',   false),
  ('c3200000-0000-0000-0000-000000000007', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000002', 'in_app', 'general',   true),
  ('c3200000-0000-0000-0000-000000000008', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000002', 'sms',    'general',   false),
  -- Priya (all enabled)
  ('c3200000-0000-0000-0000-000000000009', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000003', 'email',  'general',   true),
  ('c3200000-0000-0000-0000-000000000010', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000003', 'push',   'general',   true),
  ('c3200000-0000-0000-0000-000000000011', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000003', 'in_app', 'general',   true),
  ('c3200000-0000-0000-0000-000000000012', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000003', 'sms',    'general',   true),
  -- James (email and in_app only)
  ('c3200000-0000-0000-0000-000000000013', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000004', 'email',  'general',   true),
  ('c3200000-0000-0000-0000-000000000014', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000004', 'push',   'general',   false),
  ('c3200000-0000-0000-0000-000000000015', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000004', 'in_app', 'general',   true),
  ('c3200000-0000-0000-0000-000000000016', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000004', 'sms',    'general',   false),
  -- Elena (all enabled except sms)
  ('c3200000-0000-0000-0000-000000000017', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000005', 'email',  'general',   true),
  ('c3200000-0000-0000-0000-000000000018', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000005', 'push',   'general',   true),
  ('c3200000-0000-0000-0000-000000000019', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000005', 'in_app', 'general',   true),
  ('c3200000-0000-0000-0000-000000000020', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000005', 'sms',    'general',   false);

-- Push tokens (3) -----------------------------------------------------------------

INSERT INTO public.push_tokens (id, org_id, user_id, token, platform, device_name, is_active, last_used_at) VALUES
  ('c3300000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'ExponentPushToken[aaaa1111bbbb2222]', 'ios',     'Sarah iPhone 15',    true,  '2025-03-10 10:00:00+00'),
  ('c3300000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000003', 'fcm_token_priya_pixel8_2025',         'android', 'Priya Pixel 8',      true,  '2025-03-11 09:00:00+00'),
  ('c3300000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000005', 'web_push_elena_chrome_2025',          'web',     'Elena Chrome Desktop', true, '2025-03-12 16:00:00+00');

COMMIT;
