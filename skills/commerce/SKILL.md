---
name: commerce
description: Orders, carts, shipping records, and fulfillments for e-commerce workflows.
---

# Commerce

Orders with line items, shopping carts, shipping tracking, and fulfillment records. All monetary amounts are stored in the smallest currency unit (e.g. cents for USD). Products are referenced from the billing skill.

## Tables

### orders

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| contact_id | uuid | References contacts. Set NULL on contact delete. |
| number | text | Human-readable order number, e.g. ORD-2026-001. |
| status | order_status | Current order state. Defaults to pending. |
| currency | text | ISO currency code. Defaults to USD. |
| subtotal | numeric | Amount before tax and shipping, in smallest currency unit. Defaults to 0. |
| tax | numeric | Tax amount in smallest currency unit. Defaults to 0. |
| shipping_cost | numeric | Shipping cost in smallest currency unit. Defaults to 0. |
| total | numeric | Total amount in smallest currency unit. Defaults to 0. |
| shipping_address | jsonb | Shipping address as JSON. |
| billing_address | jsonb | Billing address as JSON. |
| placed_at | timestamptz | When the order was placed. |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

### order_items

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| order_id | uuid | References orders. Cascade delete. |
| product_id | uuid | References products. Set NULL on product delete. |
| name | text | Product name at time of purchase. |
| quantity | integer | Number of units. Defaults to 1. |
| unit_price | numeric | Price per unit in smallest currency unit. |
| total | numeric | Line total in smallest currency unit (quantity * unit_price). |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

### carts

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| contact_id | uuid | References contacts. Set NULL on contact delete. |
| status | cart_status | Cart state. Defaults to active. |
| currency | text | ISO currency code. Defaults to USD. |
| expires_at | timestamptz | When the cart expires and becomes abandoned. |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

### cart_items

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| cart_id | uuid | References carts. Cascade delete. |
| product_id | uuid | References products. Set NULL on product delete. |
| quantity | integer | Number of units. Defaults to 1. |
| unit_price | numeric | Price per unit in smallest currency unit. |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

### shipping_records

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| order_id | uuid | References orders. Cascade delete. |
| carrier | text | Shipping carrier name, e.g. UPS, FedEx, USPS. |
| tracking_number | text | Carrier tracking number. |
| status | shipping_status | Shipping state. Defaults to label_created. |
| shipped_at | timestamptz | When the shipment was dispatched. |
| delivered_at | timestamptz | When the shipment was delivered. |
| address | jsonb | Delivery address as JSON. |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

### fulfillments

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key, auto-generated. |
| org_id | uuid | References organizations. Cascade delete. |
| order_id | uuid | References orders. Cascade delete. |
| status | fulfillment_status | Fulfillment state. Defaults to pending. |
| fulfilled_by | uuid | References users. Set NULL on user delete. |
| fulfilled_at | timestamptz | When the fulfillment was completed. |
| notes | text | Internal notes about the fulfillment. |
| created_at | timestamptz | Row creation timestamp. |
| updated_at | timestamptz | Auto-updated via trigger. |
| metadata | jsonb | Arbitrary key-value data. Defaults to empty object. |

## Enums

### order_status

| Value | Description |
|-------|-------------|
| pending | Order created but not yet confirmed. |
| confirmed | Order confirmed and awaiting processing. |
| processing | Order is being prepared. |
| shipped | Order has been shipped. |
| delivered | Order has been delivered. |
| canceled | Order has been canceled. |
| refunded | Order has been refunded. |

### cart_status

| Value | Description |
|-------|-------------|
| active | Cart is active and items can be added. |
| converted | Cart was converted into an order. |
| abandoned | Cart expired or was abandoned. |

### shipping_status

| Value | Description |
|-------|-------------|
| label_created | Shipping label has been created. |
| in_transit | Shipment is in transit. |
| out_for_delivery | Shipment is out for delivery. |
| delivered | Shipment has been delivered. |
| returned | Shipment was returned to sender. |
| exception | A delivery exception occurred. |

### fulfillment_status

| Value | Description |
|-------|-------------|
| pending | Fulfillment has not started. |
| processing | Items are being packed or prepared. |
| fulfilled | All items have been fulfilled. |
| canceled | Fulfillment was canceled. |

## Row-Level Security

All six tables are scoped to the current user's organization via `get_user_org_id()`. Any org member can select, insert, and update rows. Only admins (checked via `is_admin()`) can delete rows.

## Dependencies

- **billing** -- products
- **crm** (transitive via billing) -- contacts
- **identity** (transitive via crm) -- organizations, users, `get_user_org_id()`, `is_admin()`, `set_updated_at()`

## Example Queries

Calculate total revenue by order status:

```sql
SELECT
  status,
  count(*) AS order_count,
  sum(total) / 100.0 AS total_dollars
FROM orders
GROUP BY status
ORDER BY total_dollars DESC;
```

Show cart value for all active carts:

```sql
SELECT
  c.id AS cart_id,
  con.first_name || ' ' || con.last_name AS contact,
  count(ci.id) AS item_count,
  sum(ci.quantity * ci.unit_price) / 100.0 AS cart_value_dollars,
  c.expires_at
FROM carts c
LEFT JOIN contacts con ON con.id = c.contact_id
LEFT JOIN cart_items ci ON ci.cart_id = c.id
WHERE c.status = 'active'
GROUP BY c.id, con.first_name, con.last_name, c.expires_at
ORDER BY cart_value_dollars DESC;
```

Track shipping status for an order:

```sql
SELECT
  o.number AS order_number,
  sr.carrier,
  sr.tracking_number,
  sr.status AS shipping_status,
  sr.shipped_at,
  sr.delivered_at
FROM shipping_records sr
JOIN orders o ON o.id = sr.order_id
WHERE o.id = '<order_id>'
ORDER BY sr.created_at DESC;
```

List orders awaiting fulfillment:

```sql
SELECT
  o.number AS order_number,
  o.status AS order_status,
  f.status AS fulfillment_status,
  o.total / 100.0 AS total_dollars,
  o.placed_at,
  f.notes
FROM orders o
JOIN fulfillments f ON f.order_id = o.id
WHERE f.status IN ('pending', 'processing')
ORDER BY o.placed_at ASC;
```

Revenue per product from completed orders:

```sql
SELECT
  oi.name AS product,
  sum(oi.quantity) AS units_sold,
  sum(oi.total) / 100.0 AS revenue_dollars
FROM order_items oi
JOIN orders o ON o.id = oi.order_id
WHERE o.status IN ('shipped', 'delivered')
GROUP BY oi.name
ORDER BY revenue_dollars DESC;
```

Identify abandoned carts older than 24 hours:

```sql
SELECT
  c.id AS cart_id,
  con.email,
  sum(ci.quantity * ci.unit_price) / 100.0 AS cart_value_dollars,
  c.created_at,
  c.expires_at
FROM carts c
LEFT JOIN contacts con ON con.id = c.contact_id
LEFT JOIN cart_items ci ON ci.cart_id = c.id
WHERE c.status = 'active'
  AND c.created_at < now() - interval '24 hours'
GROUP BY c.id, con.email, c.created_at, c.expires_at
ORDER BY cart_value_dollars DESC;
```
