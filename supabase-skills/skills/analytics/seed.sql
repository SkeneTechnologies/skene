-- Analytics seed data: tags, custom fields, and activity log
BEGIN;

INSERT INTO public.tags (id, org_id, name, color) VALUES
  ('b2000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'Enterprise',   '#7c3aed'),
  ('b2000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'High Priority', '#ef4444'),
  ('b2000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'Upsell',       '#f59e0b'),
  ('b2000000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000001', 'Strategic',    '#3b82f6'),
  ('b2000000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-000000000001', 'At Risk',      '#f97316');

INSERT INTO public.taggings (org_id, tag_id, entity_type, entity_id) VALUES
  ('a0000000-0000-0000-0000-000000000001', 'b2000000-0000-0000-0000-000000000001', 'deal',    'a3000000-0000-0000-0000-000000000001'),
  ('a0000000-0000-0000-0000-000000000001', 'b2000000-0000-0000-0000-000000000001', 'deal',    'a3000000-0000-0000-0000-000000000005'),
  ('a0000000-0000-0000-0000-000000000001', 'b2000000-0000-0000-0000-000000000002', 'ticket',  'a6000000-0000-0000-0000-000000000001'),
  ('a0000000-0000-0000-0000-000000000001', 'b2000000-0000-0000-0000-000000000003', 'company', 'f1000000-0000-0000-0000-000000000001'),
  ('a0000000-0000-0000-0000-000000000001', 'b2000000-0000-0000-0000-000000000004', 'company', 'f1000000-0000-0000-0000-000000000007'),
  ('a0000000-0000-0000-0000-000000000001', 'b2000000-0000-0000-0000-000000000004', 'deal',    'a3000000-0000-0000-0000-000000000005'),
  ('a0000000-0000-0000-0000-000000000001', 'b2000000-0000-0000-0000-000000000005', 'ticket',  'a6000000-0000-0000-0000-000000000002');

INSERT INTO public.custom_field_definitions (id, org_id, entity_type, name, field_type, description, options) VALUES
  ('b3000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'contact', 'LinkedIn URL',    'url',    'Contact LinkedIn profile URL', NULL),
  ('b3000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'deal',    'Deal Source',     'select', 'How this deal originated',     '["Inbound", "Outbound", "Referral", "Partner", "Event"]'),
  ('b3000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'company', 'Contract Renewal','date',   'Next contract renewal date',   NULL);

INSERT INTO public.custom_field_values (org_id, field_id, entity_type, entity_id, value_text) VALUES
  ('a0000000-0000-0000-0000-000000000001', 'b3000000-0000-0000-0000-000000000001', 'contact', 'f2000000-0000-0000-0000-000000000001', 'https://linkedin.com/in/alice-nakamura'),
  ('a0000000-0000-0000-0000-000000000001', 'b3000000-0000-0000-0000-000000000001', 'contact', 'f2000000-0000-0000-0000-000000000007', 'https://linkedin.com/in/grace-abadi'),
  ('a0000000-0000-0000-0000-000000000001', 'b3000000-0000-0000-0000-000000000002', 'deal',    'a3000000-0000-0000-0000-000000000001', 'Inbound'),
  ('a0000000-0000-0000-0000-000000000001', 'b3000000-0000-0000-0000-000000000002', 'deal',    'a3000000-0000-0000-0000-000000000002', 'Event'),
  ('a0000000-0000-0000-0000-000000000001', 'b3000000-0000-0000-0000-000000000002', 'deal',    'a3000000-0000-0000-0000-000000000005', 'Referral');

INSERT INTO public.custom_field_values (org_id, field_id, entity_type, entity_id, value_date) VALUES
  ('a0000000-0000-0000-0000-000000000001', 'b3000000-0000-0000-0000-000000000003', 'company', 'f1000000-0000-0000-0000-000000000001', '2027-01-15'),
  ('a0000000-0000-0000-0000-000000000001', 'b3000000-0000-0000-0000-000000000003', 'company', 'f1000000-0000-0000-0000-000000000004', '2027-03-01');

INSERT INTO public.activities (org_id, actor_id, entity_type, entity_id, action, description, changes, occurred_at) VALUES
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'deal', 'a3000000-0000-0000-0000-000000000001', 'created',        'Created deal: TechVista Enterprise License',          NULL, now() - interval '45 days'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'deal', 'a3000000-0000-0000-0000-000000000001', 'stage_changed',  'Moved from Lead to Qualified',                        '{"stage": {"from": "Lead", "to": "Qualified"}}', now() - interval '35 days'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'deal', 'a3000000-0000-0000-0000-000000000001', 'stage_changed',  'Moved from Qualified to Proposal',                    '{"stage": {"from": "Qualified", "to": "Proposal"}}', now() - interval '20 days'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'deal', 'a3000000-0000-0000-0000-000000000001', 'stage_changed',  'Moved from Proposal to Negotiation',                  '{"stage": {"from": "Proposal", "to": "Negotiation"}}', now() - interval '7 days'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'deal', 'a3000000-0000-0000-0000-000000000001', 'email_sent',     'Sent contract proposal to Alice Nakamura',            NULL, now() - interval '40 days'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'deal', 'a3000000-0000-0000-0000-000000000001', 'email_received', 'Received reply from Alice Nakamura',                  NULL, now() - interval '38 days'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'deal', 'a3000000-0000-0000-0000-000000000001', 'note_added',     'Alice confirmed 200-seat requirement. Bob joining next call.', NULL, now() - interval '37 days'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000002', 'deal', 'a3000000-0000-0000-0000-000000000002', 'created',        'Created deal: GreenLeaf Analytics Platform',          NULL, now() - interval '30 days'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000002', 'deal', 'a3000000-0000-0000-0000-000000000002', 'stage_changed',  'Moved from Lead to Qualified',                        '{"stage": {"from": "Lead", "to": "Qualified"}}', now() - interval '22 days'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'deal', 'a3000000-0000-0000-0000-000000000003', 'deal_won',       'Closed won: Pinnacle Finance Annual Contract',        '{"value": 8500000}', now() - interval '15 days'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'deal', 'a3000000-0000-0000-0000-000000000005', 'created',        'Created deal: Orion Aerospace Platform Expansion',    NULL, now() - interval '60 days'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'deal', 'a3000000-0000-0000-0000-000000000005', 'stage_changed',  'Moved from Lead to Qualified',                        '{"stage": {"from": "Lead", "to": "Qualified"}}', now() - interval '50 days'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'deal', 'a3000000-0000-0000-0000-000000000005', 'stage_changed',  'Moved from Qualified to Proposal',                    '{"stage": {"from": "Qualified", "to": "Proposal"}}', now() - interval '35 days'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000002', 'contact', 'f2000000-0000-0000-0000-000000000003', 'created',      'Created contact: Clara Okonkwo',                      NULL, now() - interval '32 days'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000002', 'contact', 'f2000000-0000-0000-0000-000000000003', 'email_sent',   'Sent post-conference follow-up',                      NULL, now() - interval '28 days'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000002', 'contact', 'f2000000-0000-0000-0000-000000000003', 'email_received','Clara requested a demo',                               NULL, now() - interval '25 days'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000002', 'contact', 'f2000000-0000-0000-0000-000000000003', 'call_logged',  'Intro call with Clara and Sam. Very interested in analytics features.', NULL, now() - interval '20 days'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000003', 'task', 'a5000000-0000-0000-0000-000000000001', 'created',        'Created task: Design new API schema',                  NULL, now() - interval '65 days'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000003', 'task', 'a5000000-0000-0000-0000-000000000001', 'task_completed', 'Completed: Design new API schema',                     '{"status": {"from": "in_progress", "to": "done"}}', now() - interval '50 days'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000004', 'task', 'a5000000-0000-0000-0000-000000000002', 'task_completed', 'Completed: Implement auth middleware',                  '{"status": {"from": "in_progress", "to": "done"}}', now() - interval '35 days'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000003', 'task', 'a5000000-0000-0000-0000-000000000003', 'assigned',       'Assigned to James Wright',                             '{"assignee": {"from": null, "to": "James Wright"}}', now() - interval '40 days'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000005', 'ticket', 'a6000000-0000-0000-0000-000000000001', 'created',         'Created ticket: Cannot export CSV reports',         NULL, now() - interval '2 days'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000005', 'ticket', 'a6000000-0000-0000-0000-000000000002', 'created',         'Created ticket: SSO configuration not working',     NULL, now() - interval '5 days'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000005', 'ticket', 'a6000000-0000-0000-0000-000000000002', 'status_changed',  'Changed status from open to pending',               '{"status": {"from": "open", "to": "pending"}}', now() - interval '4 days'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000005', 'ticket', 'a6000000-0000-0000-0000-000000000003', 'status_changed',  'Resolved: Billing invoice formatting',              '{"status": {"from": "open", "to": "resolved"}}', now() - interval '10 days'),
  ('a0000000-0000-0000-0000-000000000001', NULL,                                  'subscription', 'ad000000-0000-0000-0000-000000000001', 'created',           'Subscription created for Pinnacle Finance',    NULL, now() - interval '30 days'),
  ('a0000000-0000-0000-0000-000000000001', NULL,                                  'invoice',      'ae000000-0000-0000-0000-000000000001', 'payment_received',  'Payment received: $49,500.00 from Pinnacle Finance', '{"amount": 4950000, "currency": "USD"}', now() - interval '20 days'),
  ('a0000000-0000-0000-0000-000000000001', NULL,                                  'subscription', 'ad000000-0000-0000-0000-000000000002', 'created',           'Subscription created for TechVista Solutions',  NULL, now() - interval '15 days'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000003', 'document', 'aa000000-0000-0000-0000-000000000001', 'created',   'Created document: Platform v2 Architecture',   NULL, now() - interval '60 days'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000004', 'document', 'aa000000-0000-0000-0000-000000000001', 'commented', 'Commented on Platform v2 Architecture',         NULL, now() - interval '55 days'),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000004', 'document', 'aa000000-0000-0000-0000-000000000002', 'created',   'Created document: API Authentication Guide',    NULL, now() - interval '45 days');

COMMIT;
