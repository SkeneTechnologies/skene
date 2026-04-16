-- Forms seed data: 3 form definitions, 10 fields, 15 submissions, 3 uploads
BEGIN;

-- Form definitions ---------------------------------------------------------------

INSERT INTO public.form_definitions (id, org_id, creator_id, name, slug, description, status, submit_message) VALUES
  ('c2000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'Contact Us',  'contact-us',  'General enquiry form for website visitors', 'active',   'Thank you for reaching out. We will respond within 24 hours.'),
  ('c2000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000002', 'NPS Survey',  'nps-survey',  'Net promoter score survey sent after onboarding', 'active',   'Thanks for your feedback.'),
  ('c2000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'Beta Signup',  'beta-signup', 'Early access registration form', 'draft', 'You are on the list. We will be in touch soon.');

-- Form fields -- contact-us (4 fields) -------------------------------------------

INSERT INTO public.form_fields (id, org_id, form_id, label, field_key, field_type, position, is_required) VALUES
  ('c2100000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'c2000000-0000-0000-0000-000000000001', 'Full Name',     'full_name',  'text',     0, true),
  ('c2100000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'c2000000-0000-0000-0000-000000000001', 'Email Address', 'email',      'email',    1, true),
  ('c2100000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'c2000000-0000-0000-0000-000000000001', 'Message',       'message',    'textarea', 2, true),
  ('c2100000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000001', 'c2000000-0000-0000-0000-000000000001', 'Attachment',    'attachment', 'file',     3, false);

-- Form fields -- nps-survey (3 fields) -------------------------------------------

INSERT INTO public.form_fields (id, org_id, form_id, label, field_key, field_type, position, is_required, options) VALUES
  ('c2100000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-000000000001', 'c2000000-0000-0000-0000-000000000002', 'Score',          'score',    'number',   0, true,  '{"min": 0, "max": 10}'),
  ('c2100000-0000-0000-0000-000000000006', 'a0000000-0000-0000-0000-000000000001', 'c2000000-0000-0000-0000-000000000002', 'What could we improve?', 'feedback', 'textarea', 1, false, null),
  ('c2100000-0000-0000-0000-000000000007', 'a0000000-0000-0000-0000-000000000001', 'c2000000-0000-0000-0000-000000000002', 'Can we follow up?', 'follow_up', 'checkbox', 2, false, null);

-- Form fields -- beta-signup (3 fields) ------------------------------------------

INSERT INTO public.form_fields (id, org_id, form_id, label, field_key, field_type, position, is_required, options) VALUES
  ('c2100000-0000-0000-0000-000000000008', 'a0000000-0000-0000-0000-000000000001', 'c2000000-0000-0000-0000-000000000003', 'Email',         'email',       'email',  0, true, null),
  ('c2100000-0000-0000-0000-000000000009', 'a0000000-0000-0000-0000-000000000001', 'c2000000-0000-0000-0000-000000000003', 'Company Name',  'company',     'text',   1, false, null),
  ('c2100000-0000-0000-0000-000000000010', 'a0000000-0000-0000-0000-000000000001', 'c2000000-0000-0000-0000-000000000003', 'Use Case',      'use_case',    'select', 2, true, '[{"value":"saas","label":"SaaS Product"},{"value":"ecommerce","label":"E-commerce"},{"value":"internal","label":"Internal Tool"}]');

-- Form submissions -- contact-us (5) ---------------------------------------------

INSERT INTO public.form_submissions (id, org_id, form_id, data, submitted_at, ip_address, user_agent) VALUES
  ('c2200000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'c2000000-0000-0000-0000-000000000001', '{"full_name":"Alice Park","email":"alice@example.com","message":"Interested in enterprise pricing."}',   '2025-03-01 10:15:00+00', '203.0.113.10', 'Mozilla/5.0'),
  ('c2200000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'c2000000-0000-0000-0000-000000000001', '{"full_name":"Bob Lee","email":"bob@example.com","message":"How does SSO integration work?"}',           '2025-03-02 14:30:00+00', '198.51.100.5', 'Mozilla/5.0'),
  ('c2200000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'c2000000-0000-0000-0000-000000000001', '{"full_name":"Carla Diaz","email":"carla@example.com","message":"Can I get a demo of the product?"}',    '2025-03-05 09:00:00+00', '192.0.2.44',   'Mozilla/5.0'),
  ('c2200000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000001', 'c2000000-0000-0000-0000-000000000001', '{"full_name":"Dan Okoro","email":"dan@example.com","message":"We need HIPAA compliance details."}',      '2025-03-07 16:45:00+00', '203.0.113.88', 'Mozilla/5.0'),
  ('c2200000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-000000000001', 'c2000000-0000-0000-0000-000000000001', '{"full_name":"Eva Muller","email":"eva@example.com","message":"What regions are supported?"}',            '2025-03-10 11:20:00+00', '198.51.100.9', 'Mozilla/5.0');

-- Form submissions -- nps-survey (5) ---------------------------------------------

INSERT INTO public.form_submissions (id, org_id, form_id, data, submitted_at) VALUES
  ('c2200000-0000-0000-0000-000000000006', 'a0000000-0000-0000-0000-000000000001', 'c2000000-0000-0000-0000-000000000002', '{"score":9,"feedback":"Onboarding was smooth.","follow_up":true}',       '2025-03-03 08:00:00+00'),
  ('c2200000-0000-0000-0000-000000000007', 'a0000000-0000-0000-0000-000000000001', 'c2000000-0000-0000-0000-000000000002', '{"score":7,"feedback":"Docs could use more examples.","follow_up":false}', '2025-03-04 12:00:00+00'),
  ('c2200000-0000-0000-0000-000000000008', 'a0000000-0000-0000-0000-000000000001', 'c2000000-0000-0000-0000-000000000002', '{"score":10,"feedback":null,"follow_up":true}',                          '2025-03-06 15:30:00+00'),
  ('c2200000-0000-0000-0000-000000000009', 'a0000000-0000-0000-0000-000000000001', 'c2000000-0000-0000-0000-000000000002', '{"score":6,"feedback":"Migration was tricky.","follow_up":true}',          '2025-03-08 09:15:00+00'),
  ('c2200000-0000-0000-0000-000000000010', 'a0000000-0000-0000-0000-000000000001', 'c2000000-0000-0000-0000-000000000002', '{"score":8,"feedback":"Good overall.","follow_up":false}',                 '2025-03-09 17:00:00+00');

-- Form submissions -- beta-signup (5) --------------------------------------------

INSERT INTO public.form_submissions (id, org_id, form_id, data, submitted_at) VALUES
  ('c2200000-0000-0000-0000-000000000011', 'a0000000-0000-0000-0000-000000000001', 'c2000000-0000-0000-0000-000000000003', '{"email":"frank@startup.io","company":"Startup Inc","use_case":"saas"}',       '2025-03-11 10:00:00+00'),
  ('c2200000-0000-0000-0000-000000000012', 'a0000000-0000-0000-0000-000000000001', 'c2000000-0000-0000-0000-000000000003', '{"email":"gina@shop.co","company":"ShopCo","use_case":"ecommerce"}',            '2025-03-12 14:00:00+00'),
  ('c2200000-0000-0000-0000-000000000013', 'a0000000-0000-0000-0000-000000000001', 'c2000000-0000-0000-0000-000000000003', '{"email":"hank@bigcorp.com","company":"BigCorp","use_case":"internal"}',        '2025-03-13 08:30:00+00'),
  ('c2200000-0000-0000-0000-000000000014', 'a0000000-0000-0000-0000-000000000001', 'c2000000-0000-0000-0000-000000000003', '{"email":"iris@devhub.dev","company":"DevHub","use_case":"saas"}',               '2025-03-14 11:45:00+00'),
  ('c2200000-0000-0000-0000-000000000015', 'a0000000-0000-0000-0000-000000000001', 'c2000000-0000-0000-0000-000000000003', '{"email":"jack@agency.com","company":"The Agency","use_case":"internal"}',      '2025-03-15 16:00:00+00');

-- Form uploads (3) ---------------------------------------------------------------

INSERT INTO public.form_uploads (id, org_id, submission_id, field_id, file_name, file_size, mime_type, storage_path) VALUES
  ('c2300000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'c2200000-0000-0000-0000-000000000001', 'c2100000-0000-0000-0000-000000000004', 'requirements.pdf',  204800,  'application/pdf',  'forms/contact-us/c2200000-0000-0000-0000-000000000001/requirements.pdf'),
  ('c2300000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'c2200000-0000-0000-0000-000000000004', 'c2100000-0000-0000-0000-000000000004', 'compliance-checklist.xlsx', 102400, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'forms/contact-us/c2200000-0000-0000-0000-000000000004/compliance-checklist.xlsx'),
  ('c2300000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'c2200000-0000-0000-0000-000000000003', 'c2100000-0000-0000-0000-000000000004', 'screenshot.png',    51200,   'image/png',        'forms/contact-us/c2200000-0000-0000-0000-000000000003/screenshot.png');

COMMIT;
