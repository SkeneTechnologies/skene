-- Commerce seed data: 5 orders, line items, 2 carts, shipping records, fulfillments
BEGIN;

-- Orders (5 orders across different contacts)
INSERT INTO public.orders (id, org_id, contact_id, number, status, currency, subtotal, tax, shipping_cost, total, shipping_address, billing_address, placed_at) VALUES
  ('c5000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'f2000000-0000-0000-0000-000000000001', 'ORD-2026-001', 'delivered', 'USD', 8800, 704, 500, 10004, '{"line1": "100 Tech Blvd", "city": "San Francisco", "state": "CA", "zip": "94105"}'::jsonb, '{"line1": "100 Tech Blvd", "city": "San Francisco", "state": "CA", "zip": "94105"}'::jsonb, now() - interval '30 days'),
  ('c5000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'f2000000-0000-0000-0000-000000000007', 'ORD-2026-002', 'shipped',   'USD', 5800, 464, 500, 6764,  '{"line1": "200 Finance Ave", "city": "New York", "state": "NY", "zip": "10001"}'::jsonb, '{"line1": "200 Finance Ave", "city": "New York", "state": "NY", "zip": "10001"}'::jsonb, now() - interval '10 days'),
  ('c5000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'f2000000-0000-0000-0000-000000000003', 'ORD-2026-003', 'processing','USD', 2900, 232, 0,    3132,  '{"line1": "50 Data Lane", "city": "Austin", "state": "TX", "zip": "73301"}'::jsonb, '{"line1": "50 Data Lane", "city": "Austin", "state": "TX", "zip": "73301"}'::jsonb, now() - interval '3 days'),
  ('c5000000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000001', 'f2000000-0000-0000-0000-000000000013', 'ORD-2026-004', 'confirmed', 'USD', 14700, 1176, 1000, 16876, '{"line1": "1 Aerospace Dr", "city": "Houston", "state": "TX", "zip": "77001"}'::jsonb, '{"line1": "1 Aerospace Dr", "city": "Houston", "state": "TX", "zip": "77001"}'::jsonb, now() - interval '1 day'),
  ('c5000000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-000000000001', 'f2000000-0000-0000-0000-000000000009', 'ORD-2026-005', 'canceled',  'USD', 9900, 792, 500, 11192, '{"line1": "75 Logistics Way", "city": "Chicago", "state": "IL", "zip": "60601"}'::jsonb, '{"line1": "75 Logistics Way", "city": "Chicago", "state": "IL", "zip": "60601"}'::jsonb, now() - interval '15 days');

-- Order items (referencing products from billing)
INSERT INTO public.order_items (id, org_id, order_id, product_id, name, quantity, unit_price, total) VALUES
  ('c5100000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'c5000000-0000-0000-0000-000000000001', 'ab000000-0000-0000-0000-000000000001', 'Acme Platform - Starter', 2, 2900, 5800),
  ('c5100000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'c5000000-0000-0000-0000-000000000001', 'ab000000-0000-0000-0000-000000000002', 'Acme Platform - Pro',     1, 3000, 3000),
  ('c5100000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'c5000000-0000-0000-0000-000000000002', 'ab000000-0000-0000-0000-000000000001', 'Acme Platform - Starter', 2, 2900, 5800),
  ('c5100000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000001', 'c5000000-0000-0000-0000-000000000003', 'ab000000-0000-0000-0000-000000000001', 'Acme Platform - Starter', 1, 2900, 2900),
  ('c5100000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-000000000001', 'c5000000-0000-0000-0000-000000000004', 'ab000000-0000-0000-0000-000000000002', 'Acme Platform - Pro',     3, 3000, 9000),
  ('c5100000-0000-0000-0000-000000000006', 'a0000000-0000-0000-0000-000000000001', 'c5000000-0000-0000-0000-000000000004', 'ab000000-0000-0000-0000-000000000003', 'Acme Platform - Enterprise', 1, 5700, 5700),
  ('c5100000-0000-0000-0000-000000000007', 'a0000000-0000-0000-0000-000000000001', 'c5000000-0000-0000-0000-000000000005', 'ab000000-0000-0000-0000-000000000002', 'Acme Platform - Pro',     1, 9900, 9900);

-- Carts (2 active carts)
INSERT INTO public.carts (id, org_id, contact_id, status, currency, expires_at) VALUES
  ('c5200000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'f2000000-0000-0000-0000-000000000005', 'active', 'USD', now() + interval '7 days'),
  ('c5200000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'f2000000-0000-0000-0000-000000000011', 'active', 'USD', now() + interval '3 days');

-- Cart items
INSERT INTO public.cart_items (id, org_id, cart_id, product_id, quantity, unit_price) VALUES
  ('c5300000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'c5200000-0000-0000-0000-000000000001', 'ab000000-0000-0000-0000-000000000002', 1, 9900),
  ('c5300000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'c5200000-0000-0000-0000-000000000001', 'ab000000-0000-0000-0000-000000000001', 3, 2900),
  ('c5300000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'c5200000-0000-0000-0000-000000000002', 'ab000000-0000-0000-0000-000000000003', 1, 49900);

-- Shipping records
INSERT INTO public.shipping_records (id, org_id, order_id, carrier, tracking_number, status, shipped_at, delivered_at, address) VALUES
  ('c5400000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'c5000000-0000-0000-0000-000000000001', 'UPS',   '1Z999AA10123456784', 'delivered',   now() - interval '25 days', now() - interval '22 days', '{"line1": "100 Tech Blvd", "city": "San Francisco", "state": "CA", "zip": "94105"}'::jsonb),
  ('c5400000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'c5000000-0000-0000-0000-000000000002', 'FedEx', '794644790132',       'in_transit',  now() - interval '5 days',  NULL, '{"line1": "200 Finance Ave", "city": "New York", "state": "NY", "zip": "10001"}'::jsonb);

-- Fulfillments
INSERT INTO public.fulfillments (id, org_id, order_id, status, fulfilled_by, fulfilled_at, notes) VALUES
  ('c5500000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'c5000000-0000-0000-0000-000000000001', 'fulfilled',  'b0000000-0000-0000-0000-000000000001', now() - interval '26 days', 'Packed and shipped via UPS'),
  ('c5500000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'c5000000-0000-0000-0000-000000000002', 'processing', 'b0000000-0000-0000-0000-000000000002', NULL, 'Awaiting final item from warehouse'),
  ('c5500000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'c5000000-0000-0000-0000-000000000003', 'pending',    NULL, NULL, NULL),
  ('c5500000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000001', 'c5000000-0000-0000-0000-000000000004', 'pending',    NULL, NULL, 'Large order -- requires two shipments');

COMMIT;
