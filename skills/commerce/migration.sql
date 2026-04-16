-- commerce skill: orders, carts, shipping, and fulfillments
-- Depends on billing (products), which depends on crm (contacts).

-- =============================================================================
-- 1. Enums
-- =============================================================================

CREATE TYPE public.order_status AS ENUM ('pending', 'confirmed', 'processing', 'shipped', 'delivered', 'canceled', 'refunded');
CREATE TYPE public.cart_status AS ENUM ('active', 'converted', 'abandoned');
CREATE TYPE public.shipping_status AS ENUM ('label_created', 'in_transit', 'out_for_delivery', 'delivered', 'returned', 'exception');
CREATE TYPE public.fulfillment_status AS ENUM ('pending', 'processing', 'fulfilled', 'canceled');

-- =============================================================================
-- 2. Tables
-- =============================================================================

CREATE TABLE public.orders (
  id                uuid               PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id            uuid               NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  contact_id        uuid               REFERENCES public.contacts (id) ON DELETE SET NULL,
  number            text,
  status            public.order_status NOT NULL DEFAULT 'pending',
  currency          text               NOT NULL DEFAULT 'USD',
  subtotal          numeric            NOT NULL DEFAULT 0,
  tax               numeric            NOT NULL DEFAULT 0,
  shipping_cost     numeric            NOT NULL DEFAULT 0,
  total             numeric            NOT NULL DEFAULT 0,
  shipping_address  jsonb,
  billing_address   jsonb,
  placed_at         timestamptz,
  created_at        timestamptz        NOT NULL DEFAULT now(),
  updated_at        timestamptz        NOT NULL DEFAULT now(),
  metadata          jsonb              DEFAULT '{}'::jsonb
);

CREATE TABLE public.order_items (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid        NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  order_id    uuid        NOT NULL REFERENCES public.orders (id) ON DELETE CASCADE,
  product_id  uuid        REFERENCES public.products (id) ON DELETE SET NULL,
  name        text        NOT NULL,
  quantity    integer     NOT NULL DEFAULT 1,
  unit_price  numeric     NOT NULL,
  total       numeric     NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  metadata    jsonb       DEFAULT '{}'::jsonb
);

CREATE TABLE public.carts (
  id          uuid              PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid              NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  contact_id  uuid              REFERENCES public.contacts (id) ON DELETE SET NULL,
  status      public.cart_status NOT NULL DEFAULT 'active',
  currency    text              NOT NULL DEFAULT 'USD',
  expires_at  timestamptz,
  created_at  timestamptz       NOT NULL DEFAULT now(),
  updated_at  timestamptz       NOT NULL DEFAULT now(),
  metadata    jsonb             DEFAULT '{}'::jsonb
);

CREATE TABLE public.cart_items (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid        NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  cart_id     uuid        NOT NULL REFERENCES public.carts (id) ON DELETE CASCADE,
  product_id  uuid        REFERENCES public.products (id) ON DELETE SET NULL,
  quantity    integer     NOT NULL DEFAULT 1,
  unit_price  numeric     NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  metadata    jsonb       DEFAULT '{}'::jsonb
);

CREATE TABLE public.shipping_records (
  id               uuid                  PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid                  NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  order_id         uuid                  NOT NULL REFERENCES public.orders (id) ON DELETE CASCADE,
  carrier          text,
  tracking_number  text,
  status           public.shipping_status NOT NULL DEFAULT 'label_created',
  shipped_at       timestamptz,
  delivered_at     timestamptz,
  address          jsonb,
  created_at       timestamptz           NOT NULL DEFAULT now(),
  updated_at       timestamptz           NOT NULL DEFAULT now(),
  metadata         jsonb                 DEFAULT '{}'::jsonb
);

CREATE TABLE public.fulfillments (
  id            uuid                      PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid                      NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  order_id      uuid                      NOT NULL REFERENCES public.orders (id) ON DELETE CASCADE,
  status        public.fulfillment_status NOT NULL DEFAULT 'pending',
  fulfilled_by  uuid                      REFERENCES public.users (id) ON DELETE SET NULL,
  fulfilled_at  timestamptz,
  notes         text,
  created_at    timestamptz               NOT NULL DEFAULT now(),
  updated_at    timestamptz               NOT NULL DEFAULT now(),
  metadata      jsonb                     DEFAULT '{}'::jsonb
);

-- =============================================================================
-- 3. Indexes
-- =============================================================================

CREATE INDEX idx_orders_org_id      ON public.orders (org_id);
CREATE INDEX idx_orders_contact_id  ON public.orders (contact_id);
CREATE INDEX idx_orders_status      ON public.orders (status);

CREATE INDEX idx_order_items_org_id     ON public.order_items (org_id);
CREATE INDEX idx_order_items_order_id   ON public.order_items (order_id);
CREATE INDEX idx_order_items_product_id ON public.order_items (product_id);

CREATE INDEX idx_carts_org_id      ON public.carts (org_id);
CREATE INDEX idx_carts_contact_id  ON public.carts (contact_id);
CREATE INDEX idx_carts_status      ON public.carts (status);

CREATE INDEX idx_cart_items_org_id     ON public.cart_items (org_id);
CREATE INDEX idx_cart_items_cart_id    ON public.cart_items (cart_id);
CREATE INDEX idx_cart_items_product_id ON public.cart_items (product_id);

CREATE INDEX idx_shipping_records_org_id   ON public.shipping_records (org_id);
CREATE INDEX idx_shipping_records_order_id ON public.shipping_records (order_id);
CREATE INDEX idx_shipping_records_status   ON public.shipping_records (status);

CREATE INDEX idx_fulfillments_org_id       ON public.fulfillments (org_id);
CREATE INDEX idx_fulfillments_order_id     ON public.fulfillments (order_id);
CREATE INDEX idx_fulfillments_status       ON public.fulfillments (status);
CREATE INDEX idx_fulfillments_fulfilled_by ON public.fulfillments (fulfilled_by);

-- =============================================================================
-- 4. Triggers
-- =============================================================================

CREATE TRIGGER trg_orders_updated_at BEFORE UPDATE ON public.orders
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_order_items_updated_at BEFORE UPDATE ON public.order_items
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_carts_updated_at BEFORE UPDATE ON public.carts
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_cart_items_updated_at BEFORE UPDATE ON public.cart_items
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_shipping_records_updated_at BEFORE UPDATE ON public.shipping_records
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_fulfillments_updated_at BEFORE UPDATE ON public.fulfillments
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- =============================================================================
-- 5. Comments
-- =============================================================================

COMMENT ON TABLE public.orders IS 'Customer orders with line-item totals and addresses.';
COMMENT ON TABLE public.order_items IS 'Individual line items within an order.';
COMMENT ON TABLE public.carts IS 'Shopping carts that can be converted to orders or abandoned.';
COMMENT ON TABLE public.cart_items IS 'Items in a shopping cart with quantity and unit price.';
COMMENT ON TABLE public.shipping_records IS 'Shipping and tracking details for orders.';
COMMENT ON TABLE public.fulfillments IS 'Fulfillment records tracking order packing and dispatch.';

COMMENT ON COLUMN public.orders.number IS 'Human-readable order number, e.g. ORD-2026-001.';
COMMENT ON COLUMN public.orders.subtotal IS 'Amount before tax and shipping, in smallest currency unit.';
COMMENT ON COLUMN public.orders.tax IS 'Tax amount in smallest currency unit.';
COMMENT ON COLUMN public.orders.shipping_cost IS 'Shipping cost in smallest currency unit.';
COMMENT ON COLUMN public.orders.total IS 'Total amount in smallest currency unit (subtotal + tax + shipping).';
COMMENT ON COLUMN public.order_items.unit_price IS 'Price per unit in smallest currency unit.';
COMMENT ON COLUMN public.order_items.total IS 'Line total in smallest currency unit (quantity * unit_price).';
COMMENT ON COLUMN public.carts.expires_at IS 'When the cart expires and becomes abandoned.';
COMMENT ON COLUMN public.shipping_records.carrier IS 'Shipping carrier name, e.g. UPS, FedEx, USPS.';
COMMENT ON COLUMN public.fulfillments.notes IS 'Internal notes about the fulfillment.';

-- =============================================================================
-- 6. Row-Level Security
-- =============================================================================

ALTER TABLE public.orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.carts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cart_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.shipping_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fulfillments ENABLE ROW LEVEL SECURITY;

-- orders ----------------------------------------------------------------------

CREATE POLICY orders_select ON public.orders
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY orders_insert ON public.orders
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY orders_update ON public.orders
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY orders_delete ON public.orders
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- order_items -----------------------------------------------------------------

CREATE POLICY order_items_select ON public.order_items
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY order_items_insert ON public.order_items
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY order_items_update ON public.order_items
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY order_items_delete ON public.order_items
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- carts -----------------------------------------------------------------------

CREATE POLICY carts_select ON public.carts
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY carts_insert ON public.carts
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY carts_update ON public.carts
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY carts_delete ON public.carts
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- cart_items ------------------------------------------------------------------

CREATE POLICY cart_items_select ON public.cart_items
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY cart_items_insert ON public.cart_items
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY cart_items_update ON public.cart_items
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY cart_items_delete ON public.cart_items
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- shipping_records ------------------------------------------------------------

CREATE POLICY shipping_records_select ON public.shipping_records
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY shipping_records_insert ON public.shipping_records
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY shipping_records_update ON public.shipping_records
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY shipping_records_delete ON public.shipping_records
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- fulfillments ----------------------------------------------------------------

CREATE POLICY fulfillments_select ON public.fulfillments
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY fulfillments_insert ON public.fulfillments
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY fulfillments_update ON public.fulfillments
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY fulfillments_delete ON public.fulfillments
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());
