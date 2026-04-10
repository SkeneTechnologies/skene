-- =============================================================================
-- Migration: 00008_billing
-- Description: Products, prices, subscriptions, invoices, and payments.
--              Stripe-ready with optional integration columns.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Enums
-- -----------------------------------------------------------------------------
CREATE TYPE public.billing_interval AS ENUM ('month', 'year', 'one_time');
CREATE TYPE public.subscription_status AS ENUM ('trialing', 'active', 'past_due', 'canceled', 'unpaid');
CREATE TYPE public.invoice_status AS ENUM ('draft', 'open', 'paid', 'void', 'uncollectible');
CREATE TYPE public.payment_status AS ENUM ('pending', 'succeeded', 'failed', 'refunded');

-- -----------------------------------------------------------------------------
-- Table: products
-- Things you sell. Maps 1:1 to Stripe products if integrated.
-- -----------------------------------------------------------------------------
CREATE TABLE public.products (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  name            text NOT NULL,
  description     text,
  is_active       boolean NOT NULL DEFAULT true,
  stripe_product_id text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.products IS 'Things you sell. Optionally synced with Stripe products.';
COMMENT ON COLUMN public.products.stripe_product_id IS 'Stripe product ID for billing integration. NULL if not using Stripe.';

CREATE INDEX idx_products_org_id ON public.products(org_id);
CREATE UNIQUE INDEX idx_products_stripe ON public.products(stripe_product_id) WHERE stripe_product_id IS NOT NULL;

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.products
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: prices
-- Pricing options for products. A product can have multiple prices.
-- -----------------------------------------------------------------------------
CREATE TABLE public.prices (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  product_id      uuid NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
  name            text,
  amount          numeric NOT NULL,
  currency        text NOT NULL DEFAULT 'USD',
  interval        public.billing_interval NOT NULL DEFAULT 'month',
  interval_count  integer NOT NULL DEFAULT 1,
  trial_days      integer DEFAULT 0,
  is_active       boolean NOT NULL DEFAULT true,
  stripe_price_id text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.prices IS 'Pricing options for products. Multiple prices per product (monthly, annual, etc).';
COMMENT ON COLUMN public.prices.amount IS 'Price in smallest currency unit (cents for USD).';
COMMENT ON COLUMN public.prices.interval_count IS 'Number of intervals between charges. E.g. interval=month, count=3 means quarterly.';

CREATE INDEX idx_prices_org_id ON public.prices(org_id);
CREATE INDEX idx_prices_product_id ON public.prices(product_id);
CREATE UNIQUE INDEX idx_prices_stripe ON public.prices(stripe_price_id) WHERE stripe_price_id IS NOT NULL;

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.prices
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: subscriptions
-- Active subscriptions linking a contact/company to a price.
-- -----------------------------------------------------------------------------
CREATE TABLE public.subscriptions (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  contact_id      uuid REFERENCES public.contacts(id) ON DELETE SET NULL,
  company_id      uuid REFERENCES public.companies(id) ON DELETE SET NULL,
  price_id        uuid NOT NULL REFERENCES public.prices(id) ON DELETE CASCADE,
  status          public.subscription_status NOT NULL DEFAULT 'active',
  quantity        integer NOT NULL DEFAULT 1,
  current_period_start timestamptz,
  current_period_end   timestamptz,
  cancel_at       timestamptz,
  canceled_at     timestamptz,
  trial_start     timestamptz,
  trial_end       timestamptz,
  stripe_subscription_id text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.subscriptions IS 'Active subscriptions linking contacts/companies to prices.';
COMMENT ON COLUMN public.subscriptions.quantity IS 'Number of units (seats, licenses, etc).';

CREATE INDEX idx_subscriptions_org_id ON public.subscriptions(org_id);
CREATE INDEX idx_subscriptions_contact_id ON public.subscriptions(contact_id);
CREATE INDEX idx_subscriptions_company_id ON public.subscriptions(company_id);
CREATE INDEX idx_subscriptions_price_id ON public.subscriptions(price_id);
CREATE INDEX idx_subscriptions_status ON public.subscriptions(status);
CREATE UNIQUE INDEX idx_subscriptions_stripe ON public.subscriptions(stripe_subscription_id) WHERE stripe_subscription_id IS NOT NULL;

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.subscriptions
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: invoices
-- Billing documents. Can be generated from subscriptions or created manually.
-- -----------------------------------------------------------------------------
CREATE TABLE public.invoices (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  subscription_id uuid REFERENCES public.subscriptions(id) ON DELETE SET NULL,
  contact_id      uuid REFERENCES public.contacts(id) ON DELETE SET NULL,
  company_id      uuid REFERENCES public.companies(id) ON DELETE SET NULL,
  number          text,
  status          public.invoice_status NOT NULL DEFAULT 'draft',
  currency        text NOT NULL DEFAULT 'USD',
  subtotal        numeric NOT NULL DEFAULT 0,
  tax             numeric NOT NULL DEFAULT 0,
  total           numeric NOT NULL DEFAULT 0,
  amount_paid     numeric NOT NULL DEFAULT 0,
  amount_due      numeric NOT NULL DEFAULT 0,
  issued_at       timestamptz,
  due_at          timestamptz,
  paid_at         timestamptz,
  stripe_invoice_id text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.invoices IS 'Billing documents. Generated from subscriptions or created manually.';
COMMENT ON COLUMN public.invoices.number IS 'Human-readable invoice number (e.g. INV-2026-001).';
COMMENT ON COLUMN public.invoices.subtotal IS 'Total before tax, in smallest currency unit.';

CREATE INDEX idx_invoices_org_id ON public.invoices(org_id);
CREATE INDEX idx_invoices_subscription_id ON public.invoices(subscription_id);
CREATE INDEX idx_invoices_contact_id ON public.invoices(contact_id);
CREATE INDEX idx_invoices_company_id ON public.invoices(company_id);
CREATE INDEX idx_invoices_status ON public.invoices(status);
CREATE UNIQUE INDEX idx_invoices_stripe ON public.invoices(stripe_invoice_id) WHERE stripe_invoice_id IS NOT NULL;

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.invoices
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: payments
-- Individual payment transactions against invoices.
-- -----------------------------------------------------------------------------
CREATE TABLE public.payments (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  invoice_id      uuid REFERENCES public.invoices(id) ON DELETE SET NULL,
  amount          numeric NOT NULL,
  currency        text NOT NULL DEFAULT 'USD',
  status          public.payment_status NOT NULL DEFAULT 'pending',
  method          text,
  reference       text,
  paid_at         timestamptz,
  stripe_payment_intent_id text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.payments IS 'Individual payment transactions. Linked to invoices.';
COMMENT ON COLUMN public.payments.method IS 'Payment method (e.g. card, bank_transfer, check).';
COMMENT ON COLUMN public.payments.reference IS 'External payment reference or transaction ID.';

CREATE INDEX idx_payments_org_id ON public.payments(org_id);
CREATE INDEX idx_payments_invoice_id ON public.payments(invoice_id);
CREATE INDEX idx_payments_status ON public.payments(status);
CREATE UNIQUE INDEX idx_payments_stripe ON public.payments(stripe_payment_intent_id) WHERE stripe_payment_intent_id IS NOT NULL;

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.payments
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
