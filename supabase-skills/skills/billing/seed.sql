-- Billing seed data: 3 products, prices, subscriptions, invoices, payments
BEGIN;

INSERT INTO public.products (id, org_id, name, description, stripe_product_id) VALUES
  ('ab000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'Acme Platform - Starter', 'Up to 10 users, basic features',           'prod_starter_001'),
  ('ab000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'Acme Platform - Pro',     'Up to 100 users, advanced features + API', 'prod_pro_001'),
  ('ab000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'Acme Platform - Enterprise', 'Unlimited users, SSO, dedicated support', 'prod_enterprise_001');

INSERT INTO public.prices (id, org_id, product_id, name, amount, currency, interval, interval_count, trial_days, stripe_price_id) VALUES
  ('ac000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'ab000000-0000-0000-0000-000000000001', 'Starter Monthly',     2900, 'USD', 'month', 1, 14, 'price_starter_monthly'),
  ('ac000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'ab000000-0000-0000-0000-000000000001', 'Starter Annual',     29000, 'USD', 'year',  1, 14, 'price_starter_annual'),
  ('ac000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'ab000000-0000-0000-0000-000000000002', 'Pro Monthly',         9900, 'USD', 'month', 1, 14, 'price_pro_monthly'),
  ('ac000000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000001', 'ab000000-0000-0000-0000-000000000002', 'Pro Annual',         99000, 'USD', 'year',  1, 14, 'price_pro_annual'),
  ('ac000000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-000000000001', 'ab000000-0000-0000-0000-000000000003', 'Enterprise Monthly', 49900, 'USD', 'month', 1,  0, 'price_enterprise_monthly');

INSERT INTO public.subscriptions (id, org_id, contact_id, company_id, price_id, status, quantity, current_period_start, current_period_end, stripe_subscription_id) VALUES
  ('ad000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'f2000000-0000-0000-0000-000000000007', 'f1000000-0000-0000-0000-000000000004', 'ac000000-0000-0000-0000-000000000004', 'active', 50, now() - interval '30 days', now() + interval '335 days', 'sub_pinnacle_001'),
  ('ad000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'f2000000-0000-0000-0000-000000000001', 'f1000000-0000-0000-0000-000000000001', 'ac000000-0000-0000-0000-000000000005', 'active', 200, now() - interval '15 days', now() + interval '15 days', 'sub_techvista_001');

INSERT INTO public.invoices (id, org_id, subscription_id, contact_id, company_id, number, status, currency, subtotal, tax, total, amount_paid, amount_due, issued_at, due_at, paid_at, stripe_invoice_id) VALUES
  ('ae000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'ad000000-0000-0000-0000-000000000001', 'f2000000-0000-0000-0000-000000000007', 'f1000000-0000-0000-0000-000000000004', 'INV-2026-001', 'paid', 'USD', 4950000, 0, 4950000, 4950000, 0, now() - interval '30 days', now() - interval '15 days', now() - interval '20 days', 'in_pinnacle_001'),
  ('ae000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'ad000000-0000-0000-0000-000000000002', 'f2000000-0000-0000-0000-000000000001', 'f1000000-0000-0000-0000-000000000001', 'INV-2026-002', 'open', 'USD', 9980000, 0, 9980000, 0, 9980000, now() - interval '15 days', now() + interval '15 days', NULL, 'in_techvista_001');

INSERT INTO public.payments (id, org_id, invoice_id, amount, currency, status, method, paid_at, stripe_payment_intent_id) VALUES
  ('af000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'ae000000-0000-0000-0000-000000000001', 4950000, 'USD', 'succeeded', 'card', now() - interval '20 days', 'pi_pinnacle_001');

COMMIT;
