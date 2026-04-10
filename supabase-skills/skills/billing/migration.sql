-- billing skill: products, prices, subscriptions, invoices, payments
-- Depends on crm (contacts, companies).

-- =============================================================================
-- 1. Enums
-- =============================================================================

CREATE TYPE public.billing_interval AS ENUM ('month', 'year', 'one_time');
CREATE TYPE public.subscription_status AS ENUM ('trialing', 'active', 'past_due', 'canceled', 'unpaid');
CREATE TYPE public.invoice_status AS ENUM ('draft', 'open', 'paid', 'void', 'uncollectible');
CREATE TYPE public.payment_status AS ENUM ('pending', 'succeeded', 'failed', 'refunded');

-- =============================================================================
-- 2. Tables
-- =============================================================================

CREATE TABLE public.products (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid        NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  name             text        NOT NULL,
  description      text,
  is_active        boolean     NOT NULL DEFAULT true,
  stripe_product_id text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  metadata         jsonb       DEFAULT '{}'::jsonb
);

CREATE TABLE public.prices (
  id               uuid                   PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid                   NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  product_id       uuid                   NOT NULL REFERENCES public.products (id) ON DELETE CASCADE,
  name             text,
  amount           numeric                NOT NULL,
  currency         text                   NOT NULL DEFAULT 'USD',
  interval         public.billing_interval NOT NULL DEFAULT 'month',
  interval_count   integer                NOT NULL DEFAULT 1,
  trial_days       integer                DEFAULT 0,
  is_active        boolean                NOT NULL DEFAULT true,
  stripe_price_id  text,
  created_at       timestamptz            NOT NULL DEFAULT now(),
  updated_at       timestamptz            NOT NULL DEFAULT now(),
  metadata         jsonb                  DEFAULT '{}'::jsonb
);

CREATE TABLE public.subscriptions (
  id                     uuid                      PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                 uuid                      NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  contact_id             uuid                      REFERENCES public.contacts (id) ON DELETE SET NULL,
  company_id             uuid                      REFERENCES public.companies (id) ON DELETE SET NULL,
  price_id               uuid                      NOT NULL REFERENCES public.prices (id) ON DELETE CASCADE,
  status                 public.subscription_status NOT NULL DEFAULT 'active',
  quantity               integer                   NOT NULL DEFAULT 1,
  current_period_start   timestamptz,
  current_period_end     timestamptz,
  cancel_at              timestamptz,
  canceled_at            timestamptz,
  trial_start            timestamptz,
  trial_end              timestamptz,
  stripe_subscription_id text,
  created_at             timestamptz               NOT NULL DEFAULT now(),
  updated_at             timestamptz               NOT NULL DEFAULT now(),
  metadata               jsonb                     DEFAULT '{}'::jsonb
);

CREATE TABLE public.invoices (
  id               uuid                 PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid                 NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  subscription_id  uuid                 REFERENCES public.subscriptions (id) ON DELETE SET NULL,
  contact_id       uuid                 REFERENCES public.contacts (id) ON DELETE SET NULL,
  company_id       uuid                 REFERENCES public.companies (id) ON DELETE SET NULL,
  number           text,
  status           public.invoice_status NOT NULL DEFAULT 'draft',
  currency         text                 NOT NULL DEFAULT 'USD',
  subtotal         numeric              NOT NULL DEFAULT 0,
  tax              numeric              NOT NULL DEFAULT 0,
  total            numeric              NOT NULL DEFAULT 0,
  amount_paid      numeric              NOT NULL DEFAULT 0,
  amount_due       numeric              NOT NULL DEFAULT 0,
  issued_at        timestamptz,
  due_at           timestamptz,
  paid_at          timestamptz,
  stripe_invoice_id text,
  created_at       timestamptz          NOT NULL DEFAULT now(),
  updated_at       timestamptz          NOT NULL DEFAULT now(),
  metadata         jsonb                DEFAULT '{}'::jsonb
);

CREATE TABLE public.payments (
  id                       uuid                  PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                   uuid                  NOT NULL REFERENCES public.organizations (id) ON DELETE CASCADE,
  invoice_id               uuid                  REFERENCES public.invoices (id) ON DELETE SET NULL,
  amount                   numeric               NOT NULL,
  currency                 text                  NOT NULL DEFAULT 'USD',
  status                   public.payment_status NOT NULL DEFAULT 'pending',
  method                   text,
  reference                text,
  paid_at                  timestamptz,
  stripe_payment_intent_id text,
  created_at               timestamptz           NOT NULL DEFAULT now(),
  updated_at               timestamptz           NOT NULL DEFAULT now(),
  metadata                 jsonb                 DEFAULT '{}'::jsonb
);

-- =============================================================================
-- 3. Indexes
-- =============================================================================

CREATE INDEX idx_products_org_id ON public.products (org_id);
CREATE UNIQUE INDEX idx_products_stripe ON public.products (org_id, stripe_product_id)
  WHERE stripe_product_id IS NOT NULL;

CREATE INDEX idx_prices_org_id     ON public.prices (org_id);
CREATE INDEX idx_prices_product_id ON public.prices (product_id);
CREATE UNIQUE INDEX idx_prices_stripe ON public.prices (org_id, stripe_price_id)
  WHERE stripe_price_id IS NOT NULL;

CREATE INDEX idx_subscriptions_org_id     ON public.subscriptions (org_id);
CREATE INDEX idx_subscriptions_contact_id ON public.subscriptions (contact_id);
CREATE INDEX idx_subscriptions_company_id ON public.subscriptions (company_id);
CREATE INDEX idx_subscriptions_price_id   ON public.subscriptions (price_id);
CREATE INDEX idx_subscriptions_status     ON public.subscriptions (status);
CREATE UNIQUE INDEX idx_subscriptions_stripe ON public.subscriptions (org_id, stripe_subscription_id)
  WHERE stripe_subscription_id IS NOT NULL;

CREATE INDEX idx_invoices_org_id          ON public.invoices (org_id);
CREATE INDEX idx_invoices_subscription_id ON public.invoices (subscription_id);
CREATE INDEX idx_invoices_contact_id      ON public.invoices (contact_id);
CREATE INDEX idx_invoices_company_id      ON public.invoices (company_id);
CREATE INDEX idx_invoices_status          ON public.invoices (status);
CREATE UNIQUE INDEX idx_invoices_stripe ON public.invoices (org_id, stripe_invoice_id)
  WHERE stripe_invoice_id IS NOT NULL;

CREATE INDEX idx_payments_org_id     ON public.payments (org_id);
CREATE INDEX idx_payments_invoice_id ON public.payments (invoice_id);
CREATE INDEX idx_payments_status     ON public.payments (status);
CREATE UNIQUE INDEX idx_payments_stripe ON public.payments (org_id, stripe_payment_intent_id)
  WHERE stripe_payment_intent_id IS NOT NULL;

-- =============================================================================
-- 4. Triggers
-- =============================================================================

CREATE TRIGGER trg_products_updated_at BEFORE UPDATE ON public.products
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_prices_updated_at BEFORE UPDATE ON public.prices
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_subscriptions_updated_at BEFORE UPDATE ON public.subscriptions
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_invoices_updated_at BEFORE UPDATE ON public.invoices
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_payments_updated_at BEFORE UPDATE ON public.payments
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- =============================================================================
-- 5. Comments
-- =============================================================================

COMMENT ON COLUMN public.products.stripe_product_id IS 'NULL if not using Stripe.';
COMMENT ON COLUMN public.prices.amount IS 'In smallest currency unit (e.g. cents for USD).';
COMMENT ON COLUMN public.prices.interval_count IS 'For multi-interval billing, e.g. 3 months for quarterly.';
COMMENT ON COLUMN public.subscriptions.quantity IS 'Number of seats or licenses.';
COMMENT ON COLUMN public.invoices.number IS 'Human-readable invoice number, e.g. INV-2026-001.';
COMMENT ON COLUMN public.invoices.subtotal IS 'Before tax, in smallest currency unit.';
COMMENT ON COLUMN public.payments.method IS 'Payment method: card, bank_transfer, check, etc.';
COMMENT ON COLUMN public.payments.reference IS 'External payment reference or transaction ID.';

-- =============================================================================
-- 6. Row-Level Security
-- =============================================================================

ALTER TABLE public.products ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY;

-- products --------------------------------------------------------------------

CREATE POLICY products_select ON public.products
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY products_insert ON public.products
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY products_update ON public.products
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY products_delete ON public.products
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- prices ----------------------------------------------------------------------

CREATE POLICY prices_select ON public.prices
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY prices_insert ON public.prices
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY prices_update ON public.prices
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY prices_delete ON public.prices
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- subscriptions ---------------------------------------------------------------

CREATE POLICY subscriptions_select ON public.subscriptions
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY subscriptions_insert ON public.subscriptions
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY subscriptions_update ON public.subscriptions
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY subscriptions_delete ON public.subscriptions
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- invoices --------------------------------------------------------------------

CREATE POLICY invoices_select ON public.invoices
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY invoices_insert ON public.invoices
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY invoices_update ON public.invoices
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY invoices_delete ON public.invoices
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- payments --------------------------------------------------------------------

CREATE POLICY payments_select ON public.payments
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY payments_insert ON public.payments
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY payments_update ON public.payments
  FOR UPDATE USING (org_id = public.get_user_org_id());

CREATE POLICY payments_delete ON public.payments
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());
