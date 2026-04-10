-- Automations seed data: 3 automations with actions and runs
BEGIN;

INSERT INTO public.automations (id, org_id, creator_id, name, description, trigger_type, trigger_config, status) VALUES
  ('b4000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'New Lead Welcome Email', 'Send welcome email when a new lead is created', 'event', '{"event": "contact.created", "filter": {"type": "lead"}}', 'active'),
  ('b4000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'Stale Deal Alert',      'Alert owner when a deal has not moved stages in 14 days', 'schedule', '{"cron": "0 9 * * 1", "check": "deal.stage_age > 14d"}', 'active'),
  ('b4000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000003', 'Ticket SLA Escalation',  'Escalate ticket priority if no response in 4 hours', 'schedule', '{"cron": "*/30 * * * *", "check": "ticket.first_response_at IS NULL AND ticket.created_at < now() - 4h"}', 'active');

INSERT INTO public.automation_actions (org_id, automation_id, action_type, action_config, position) VALUES
  ('a0000000-0000-0000-0000-000000000001', 'b4000000-0000-0000-0000-000000000001', 'send_email', '{"template": "welcome_lead", "to": "{{contact.email}}"}', 0),
  ('a0000000-0000-0000-0000-000000000001', 'b4000000-0000-0000-0000-000000000001', 'create_task', '{"title": "Follow up with {{contact.first_name}}", "assignee": "{{contact.owner_id}}", "due_in_days": 3}', 1),
  ('a0000000-0000-0000-0000-000000000001', 'b4000000-0000-0000-0000-000000000002', 'send_email', '{"template": "stale_deal_alert", "to": "{{deal.owner.email}}"}', 0),
  ('a0000000-0000-0000-0000-000000000001', 'b4000000-0000-0000-0000-000000000003', 'update_field', '{"entity": "ticket", "field": "priority", "value": "high"}', 0),
  ('a0000000-0000-0000-0000-000000000001', 'b4000000-0000-0000-0000-000000000003', 'send_email', '{"template": "ticket_escalation", "to": "{{ticket.assignee.email}}"}', 1);

INSERT INTO public.automation_runs (org_id, automation_id, status, started_at, completed_at) VALUES
  ('a0000000-0000-0000-0000-000000000001', 'b4000000-0000-0000-0000-000000000001', 'completed', now() - interval '10 days', now() - interval '10 days' + interval '2 seconds'),
  ('a0000000-0000-0000-0000-000000000001', 'b4000000-0000-0000-0000-000000000002', 'completed', now() - interval '7 days',  now() - interval '7 days' + interval '5 seconds'),
  ('a0000000-0000-0000-0000-000000000001', 'b4000000-0000-0000-0000-000000000003', 'completed', now() - interval '1 day',   now() - interval '1 day' + interval '1 second');

COMMIT;
