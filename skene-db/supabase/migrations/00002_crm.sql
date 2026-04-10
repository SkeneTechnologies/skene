-- =============================================================================
-- Migration: 00002_crm
-- Description: Contacts, companies, and the join table between them.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Enums
-- -----------------------------------------------------------------------------
CREATE TYPE public.contact_type AS ENUM ('lead', 'prospect', 'customer', 'partner', 'other');

-- -----------------------------------------------------------------------------
-- Table: contacts
-- People you do business with. Not application users.
-- -----------------------------------------------------------------------------
CREATE TABLE public.contacts (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  owner_id        uuid REFERENCES public.users(id) ON DELETE SET NULL,
  first_name      text NOT NULL,
  last_name       text,
  email           text,
  phone           text,
  type            public.contact_type NOT NULL DEFAULT 'lead',
  title           text,
  source          text,
  avatar_url      text,
  address_line1   text,
  address_line2   text,
  city            text,
  state           text,
  postal_code     text,
  country         text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.contacts IS 'People you do business with. External contacts, not application users.';
COMMENT ON COLUMN public.contacts.owner_id IS 'The user responsible for this contact.';
COMMENT ON COLUMN public.contacts.type IS 'Lifecycle stage: lead, prospect, customer, partner, other.';
COMMENT ON COLUMN public.contacts.source IS 'How this contact was acquired (e.g. website, referral, trade show).';

CREATE INDEX idx_contacts_org_id ON public.contacts(org_id);
CREATE INDEX idx_contacts_owner_id ON public.contacts(owner_id);
CREATE INDEX idx_contacts_type ON public.contacts(type);
CREATE INDEX idx_contacts_email ON public.contacts(email);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.contacts
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: companies
-- Organizations your contacts work at. Not your tenant orgs.
-- -----------------------------------------------------------------------------
CREATE TABLE public.companies (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  owner_id        uuid REFERENCES public.users(id) ON DELETE SET NULL,
  name            text NOT NULL,
  domain          text,
  industry        text,
  size            text,
  website         text,
  phone           text,
  address_line1   text,
  address_line2   text,
  city            text,
  state           text,
  postal_code     text,
  country         text,
  annual_revenue  numeric,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.companies IS 'External companies your contacts work at. Not your tenant organizations.';
COMMENT ON COLUMN public.companies.size IS 'Company size bracket (e.g. 1-10, 11-50, 51-200).';
COMMENT ON COLUMN public.companies.annual_revenue IS 'Estimated annual revenue in cents or smallest currency unit.';

CREATE INDEX idx_companies_org_id ON public.companies(org_id);
CREATE INDEX idx_companies_owner_id ON public.companies(owner_id);
CREATE INDEX idx_companies_domain ON public.companies(domain);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.companies
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Table: contact_companies
-- Many-to-many: a contact can work at multiple companies over time.
-- -----------------------------------------------------------------------------
CREATE TABLE public.contact_companies (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  contact_id      uuid NOT NULL REFERENCES public.contacts(id) ON DELETE CASCADE,
  company_id      uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
  title           text,
  is_primary      boolean NOT NULL DEFAULT false,
  started_at      date,
  ended_at        date,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  metadata        jsonb DEFAULT '{}'::jsonb,
  UNIQUE(contact_id, company_id)
);

COMMENT ON TABLE public.contact_companies IS 'Links contacts to companies with role and tenure.';
COMMENT ON COLUMN public.contact_companies.is_primary IS 'Whether this is the contacts current primary company.';

CREATE INDEX idx_contact_companies_org_id ON public.contact_companies(org_id);
CREATE INDEX idx_contact_companies_contact_id ON public.contact_companies(contact_id);
CREATE INDEX idx_contact_companies_company_id ON public.contact_companies(company_id);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.contact_companies
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
