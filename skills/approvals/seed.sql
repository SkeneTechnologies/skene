-- Approvals seed data: two chains with steps, requests, decisions, and a delegation
BEGIN;

-- Chains
INSERT INTO public.approval_chains (id, org_id, name, description, entity_type, is_active) VALUES
  ('c7000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'Expense Approval',  'Standard approval flow for expense reports.',  'expense',  true),
  ('c7000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'Contract Approval', 'Legal and finance review for new contracts.',   'contract', true);

-- Steps -- expense chain: manager then finance
INSERT INTO public.approval_steps (id, org_id, chain_id, position, approver_id, approver_role, is_required) VALUES
  ('c7000000-0000-0000-0000-000000000010', 'a0000000-0000-0000-0000-000000000001', 'c7000000-0000-0000-0000-000000000001', 1, 'b0000000-0000-0000-0000-000000000004', NULL,      true),
  ('c7000000-0000-0000-0000-000000000011', 'a0000000-0000-0000-0000-000000000001', 'c7000000-0000-0000-0000-000000000001', 2, NULL, 'finance', true);

-- Steps -- contract chain: legal, finance, then executive
INSERT INTO public.approval_steps (id, org_id, chain_id, position, approver_id, approver_role, is_required) VALUES
  ('c7000000-0000-0000-0000-000000000012', 'a0000000-0000-0000-0000-000000000001', 'c7000000-0000-0000-0000-000000000002', 1, NULL, 'legal',     true),
  ('c7000000-0000-0000-0000-000000000013', 'a0000000-0000-0000-0000-000000000001', 'c7000000-0000-0000-0000-000000000002', 2, NULL, 'finance',   true),
  ('c7000000-0000-0000-0000-000000000014', 'a0000000-0000-0000-0000-000000000001', 'c7000000-0000-0000-0000-000000000002', 3, 'b0000000-0000-0000-0000-000000000003', NULL, false);

-- Requests
INSERT INTO public.approval_requests (id, org_id, chain_id, entity_type, entity_id, requester_id, status, submitted_at, resolved_at) VALUES
  ('c7000000-0000-0000-0000-000000000020', 'a0000000-0000-0000-0000-000000000001', 'c7000000-0000-0000-0000-000000000001', 'expense',  'c7000000-0000-0000-0000-0000000000e1', 'b0000000-0000-0000-0000-000000000005', 'approved', now() - interval '30 days', now() - interval '28 days'),
  ('c7000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000001', 'c7000000-0000-0000-0000-000000000001', 'expense',  'c7000000-0000-0000-0000-0000000000e2', 'b0000000-0000-0000-0000-000000000005', 'pending',  now() - interval '3 days',  NULL),
  ('c7000000-0000-0000-0000-000000000022', 'a0000000-0000-0000-0000-000000000001', 'c7000000-0000-0000-0000-000000000001', 'expense',  'c7000000-0000-0000-0000-0000000000e3', 'b0000000-0000-0000-0000-000000000004', 'rejected', now() - interval '15 days', now() - interval '14 days'),
  ('c7000000-0000-0000-0000-000000000023', 'a0000000-0000-0000-0000-000000000001', 'c7000000-0000-0000-0000-000000000002', 'contract', 'c7000000-0000-0000-0000-0000000000c1', 'b0000000-0000-0000-0000-000000000003', 'pending',  now() - interval '5 days',  NULL),
  ('c7000000-0000-0000-0000-000000000024', 'a0000000-0000-0000-0000-000000000001', 'c7000000-0000-0000-0000-000000000002', 'contract', 'c7000000-0000-0000-0000-0000000000c2', 'b0000000-0000-0000-0000-000000000004', 'canceled', now() - interval '20 days', now() - interval '19 days');

-- Decisions
INSERT INTO public.approval_decisions (id, org_id, request_id, step_id, decided_by, decision, comment, decided_at) VALUES
  ('c7000000-0000-0000-0000-000000000030', 'a0000000-0000-0000-0000-000000000001', 'c7000000-0000-0000-0000-000000000020', 'c7000000-0000-0000-0000-000000000010', 'b0000000-0000-0000-0000-000000000004', 'approved', 'Amounts look correct.',             now() - interval '29 days'),
  ('c7000000-0000-0000-0000-000000000031', 'a0000000-0000-0000-0000-000000000001', 'c7000000-0000-0000-0000-000000000020', 'c7000000-0000-0000-0000-000000000011', 'b0000000-0000-0000-0000-000000000003', 'approved', 'Budget confirmed.',                  now() - interval '28 days'),
  ('c7000000-0000-0000-0000-000000000032', 'a0000000-0000-0000-0000-000000000001', 'c7000000-0000-0000-0000-000000000022', 'c7000000-0000-0000-0000-000000000010', 'b0000000-0000-0000-0000-000000000004', 'rejected', 'Missing receipts for hotel charges.', now() - interval '14 days'),
  ('c7000000-0000-0000-0000-000000000033', 'a0000000-0000-0000-0000-000000000001', 'c7000000-0000-0000-0000-000000000023', 'c7000000-0000-0000-0000-000000000012', 'b0000000-0000-0000-0000-000000000005', 'approved', 'Legal terms reviewed and accepted.',  now() - interval '3 days');

-- Delegation
INSERT INTO public.approval_delegations (id, org_id, delegator_id, delegate_id, chain_id, starts_at, ends_at, reason, is_active) VALUES
  ('c7000000-0000-0000-0000-000000000040', 'a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000004', 'b0000000-0000-0000-0000-000000000005', 'c7000000-0000-0000-0000-000000000001', now() - interval '2 days', now() + interval '12 days', 'Out of office -- delegating expense approvals.', true);

COMMIT;
