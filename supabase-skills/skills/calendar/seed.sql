-- Calendar seed data: 3 events with attendees
BEGIN;

INSERT INTO public.events (id, org_id, creator_id, entity_type, entity_id, title, description, location, status, starts_at, ends_at) VALUES
  ('b1000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'deal',    'a3000000-0000-0000-0000-000000000001', 'TechVista Contract Review',       'Final contract review with Alice and Bob',            'Zoom',           'confirmed', now() + interval '3 days', now() + interval '3 days' + interval '1 hour'),
  ('b1000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000002', 'contact', 'f2000000-0000-0000-0000-000000000003', 'GreenLeaf Demo',                  'Product demo for Clara and Sam',                      'Google Meet',    'confirmed', now() + interval '5 days', now() + interval '5 days' + interval '45 minutes'),
  ('b1000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000003', NULL,      NULL,                                  'Engineering Weekly Standup',       'Recurring team sync',                                 'Slack Huddle',   'confirmed', now() + interval '1 day', now() + interval '1 day' + interval '30 minutes');

INSERT INTO public.event_attendees (org_id, event_id, user_id, contact_id, response, is_organizer) VALUES
  ('a0000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', NULL,                                  'accepted', true),
  ('a0000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000001', NULL,                                  'f2000000-0000-0000-0000-000000000001', 'accepted', false),
  ('a0000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000001', NULL,                                  'f2000000-0000-0000-0000-000000000002', 'tentative',false),
  ('a0000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000002', 'b0000000-0000-0000-0000-000000000002', NULL,                                  'accepted', true),
  ('a0000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000002', NULL,                                  'f2000000-0000-0000-0000-000000000003', 'accepted', false),
  ('a0000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000002', NULL,                                  'f2000000-0000-0000-0000-000000000019', 'pending',  false),
  ('a0000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000003', 'b0000000-0000-0000-0000-000000000003', NULL,                                  'accepted', true),
  ('a0000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000003', 'b0000000-0000-0000-0000-000000000004', NULL,                                  'accepted', false);

COMMIT;
