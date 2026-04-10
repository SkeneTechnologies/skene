---
name: billing
description: Products, prices, subscriptions, invoices, and payments with optional Stripe integration.
---

# Billing

Products, tiered prices, subscriptions, invoices, and payments. All monetary amounts are stored in the smallest currency unit (e.g. cents for USD). Each table includes an optional Stripe ID column for syncing with Stripe, but Stripe is not required.

## Tables

### products

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| name | text | Product name. |
| description | text | Optional product description. |
| is_active | boolean | Whether the product is available for new subscriptions. Defaults to true. |
| stripe_product_id | text | Stripe product ID. NULL if not using Stripe. Unique per org when set. |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

### prices

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| product_id | uuid | References products. Cascade delete. |
| name | text | Optional price tier name (e.g. "Starter", "Pro"). |
| amount | numeric | Price in smallest currency unit (e.g. cents). |
| currency | text | ISO currency code. Defaults to USD. |
| interval | billing_interval | Billing frequency. Defaults to month. |
| interval_count | integer | Number of intervals per billing cycle (e.g. 3 for quarterly). Defaults to 1. |
| trial_days | integer | Free trial length in days. Defaults to 0. |
| is_active | boolean | Whether this price is available for new subscriptions. Defaults to true. |
| stripe_price_id | text | Stripe price ID. NULL if not using Stripe. Unique per org when set. |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

### subscriptions

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| contact_id | uuid | References contacts. Set NULL on contact delete. |
| company_id | uuid | References companies. Set NULL on company delete. |
| price_id | uuid | References prices. Cascade delete. |
| status | subscription_status | Current subscription state. Defaults to active. |
| quantity | integer | Number of seats or licenses. Defaults to 1. |
| current_period_start | timestamptz | Start of the current billing period. |
| current_period_end | timestamptz | End of the current billing period. |
| cancel_at | timestamptz | Scheduled cancellation date. |
| canceled_at | timestamptz | Actual cancellation timestamp. |
| trial_start | timestamptz | Trial period start. |
| trial_end | timestamptz | Trial period end. |
| stripe_subscription_id | text | Stripe subscription ID. Unique per org when set. |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

### invoices

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| subscription_id | uuid | References subscriptions. Set NULL on subscription delete. |
| contact_id | uuid | References contacts. Set NULL on contact delete. |
| company_id | uuid | References companies. Set NULL on company delete. |
| number | text | Human-readable invoice number (e.g. INV-2026-001). |
| status | invoice_status | Invoice state. Defaults to draft. |
| currency | text | ISO currency code. Defaults to USD. |
| subtotal | numeric | Amount before tax, in smallest currency unit. Defaults to 0. |
| tax | numeric | Tax amount, in smallest currency unit. Defaults to 0. |
| total | numeric | Total amount, in smallest currency unit. Defaults to 0. |
| amount_paid | numeric | Amount already paid. Defaults to 0. |
| amount_due | numeric | Remaining balance. Defaults to 0. |
| issued_at | timestamptz | Date the invoice was sent. |
| due_at | timestamptz | Payment due date. |
| paid_at | timestamptz | Date payment was received. |
| stripe_invoice_id | text | Stripe invoice ID. Unique per org when set. |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

### payments

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| invoice_id | uuid | References invoices. Set NULL on invoice delete. |
| amount | numeric | Payment amount in smallest currency unit. |
| currency | text | ISO currency code. Defaults to USD. |
| status | payment_status | Payment state. Defaults to pending. |
| method | text | Payment method: card, bank_transfer, check, etc. |
| reference | text | External payment reference or transaction ID. |
| paid_at | timestamptz | Timestamp when payment was received. |
| stripe_payment_intent_id | text | Stripe PaymentIntent ID. Unique per org when set. |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

## Enums

### billing_interval

| Value | Description |
|-------|-------------|
| month | Monthly billing cycle. |
| year | Annual billing cycle. |
| one_time | Single charge, no recurrence. |

### subscription_status

| Value | Description |
|-------|-------------|
| trialing | Subscription is in a free trial period. |
| active | Subscription is active and billing normally. |
| past_due | Payment failed but subscription has not been canceled yet. |
| canceled | Subscription has been canceled. |
| unpaid | Subscription is unpaid and suspended. |

### invoice_status

| Value | Description |
|-------|-------------|
| draft | Invoice is being prepared and not yet sent. |
| open | Invoice has been sent and is awaiting payment. |
| paid | Invoice has been paid in full. |
| void | Invoice has been voided and is no longer valid. |
| uncollectible | Invoice has been written off as uncollectible. |

### payment_status

| Value | Description |
|-------|-------------|
| pending | Payment has been initiated but not yet confirmed. |
| succeeded | Payment completed successfully. |
| failed | Payment attempt failed. |
| refunded | Payment has been refunded. |

## Row-Level Security

All five tables are scoped to the current user's organization via `get_user_org_id()`. Any org member can select, insert, and update rows. Only admins (checked via `is_admin()`) can delete products, prices, subscriptions, invoices, or payments.

## Dependencies

- **crm** -- contacts, companies
- **identity** (transitive via crm) -- organizations, users, `get_user_org_id()`, `is_admin()`, `set_updated_at()`

## Example Queries

Calculate monthly recurring revenue (MRR) across all active subscriptions:

```sql
SELECT
  sum(
    CASE p.interval
      WHEN 'month' THEN p.amount * s.quantity
      WHEN 'year'  THEN (p.amount * s.quantity) / 12
      ELSE 0
    END
  ) / 100.0 AS mrr_dollars
FROM subscriptions s
JOIN prices p ON p.id = s.price_id
WHERE s.status = 'active';
```

Break down annual recurring revenue (ARR) by product:

```sql
SELECT
  pr.name AS product,
  count(s.id) AS active_subscriptions,
  sum(s.quantity) AS total_seats,
  sum(
    CASE p.interval
      WHEN 'month' THEN p.amount * s.quantity * 12
      WHEN 'year'  THEN p.amount * s.quantity
      ELSE p.amount * s.quantity
    END
  ) / 100.0 AS arr_dollars
FROM products pr
JOIN prices p ON p.product_id = pr.id
JOIN subscriptions s ON s.price_id = p.id AND s.status = 'active'
GROUP BY pr.id, pr.name
ORDER BY arr_dollars DESC;
```

List outstanding invoices with urgency classification:

```sql
SELECT
  i.number,
  co.name AS company,
  i.total / 100.0 AS total_dollars,
  i.amount_due / 100.0 AS due_dollars,
  i.due_at,
  CASE
    WHEN i.due_at < now() THEN 'overdue'
    WHEN i.due_at < now() + interval '7 days' THEN 'due_soon'
    ELSE 'upcoming'
  END AS urgency
FROM invoices i
LEFT JOIN companies co ON co.id = i.company_id
WHERE i.status IN ('open', 'past_due')
ORDER BY i.due_at ASC;
```

Show payment history for a specific invoice:

```sql
SELECT
  p.id,
  p.amount / 100.0 AS amount_dollars,
  p.currency,
  p.status,
  p.method,
  p.reference,
  p.paid_at
FROM payments p
WHERE p.invoice_id = '<invoice_id>'
ORDER BY p.created_at ASC;
```

List subscriptions expiring within the next 30 days:

```sql
SELECT
  s.id,
  co.name AS company,
  pr.name AS product,
  s.quantity AS seats,
  s.status,
  s.current_period_end
FROM subscriptions s
JOIN prices p ON p.id = s.price_id
JOIN products pr ON pr.id = p.product_id
LEFT JOIN companies co ON co.id = s.company_id
WHERE s.status = 'active'
  AND s.current_period_end < now() + interval '30 days'
ORDER BY s.current_period_end ASC;
```
