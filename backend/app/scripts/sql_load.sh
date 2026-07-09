#!/usr/bin/env bash
set -euo pipefail
# Pure SQL batch loader — single session per batch
MERCHANT="f17cc48d-8a76-4d63-b07a-b2aaacc7afe5"
BATCH="${BATCH_SIZE:-10000}"
export PGPASSWORD=girdersoft

psql_one() {
  psql -h localhost -p 5433 -U girdersoft -d returnshield -v ON_ERROR_STOP=1 -t -A -c "$1"
}

TOTAL=$(psql_one "SELECT count(*) FROM staging")
echo "=== SQL Batch Load: $TOTAL rows, batch=$BATCH ==="

OFFSET=0
while [ "$OFFSET" -lt "$TOTAL" ]; do
  B=$(printf "%'d" $OFFSET)
  echo "--- Batch at row $B ---"
  t0=$(date +%s)

  psql -h localhost -p 5433 -U girdersoft -d returnshield -v ON_ERROR_STOP=1 -t -A <<SQL
-- Materialize batch
DROP TABLE IF EXISTS _batch;
CREATE TEMP TABLE _batch AS
SELECT * FROM staging
ORDER BY customer_id, order_id, return_date
LIMIT $BATCH OFFSET $OFFSET;

-- 1. Customers
INSERT INTO customers (id, merchant_id, external_customer_id, name, email_hash, phone_hash)
SELECT DISTINCT ON (s.customer_id)
  md5('c:' || s.customer_id)::uuid, '$MERCHANT'::uuid,
  s.customer_id, s.customer_name,
  encode(digest(s.customer_email, 'sha256'), 'hex'),
  encode(digest(s.customer_phone, 'sha256'), 'hex')
FROM _batch s
WHERE NOT EXISTS (SELECT 1 FROM customers c WHERE c.external_customer_id = s.customer_id AND c.merchant_id = '$MERCHANT'::uuid)
ON CONFLICT (id) DO NOTHING;

-- 2. Customer identities
INSERT INTO customer_identities (id, customer_id, merchant_id, identity_type, identity_value_hash)
SELECT DISTINCT ON (s.customer_id, typ.val)
  md5('i:' || s.customer_id || ':' || typ.val)::uuid, c.id, '$MERCHANT'::uuid,
  typ.val,
  encode(digest(CASE typ.val
    WHEN 'email' THEN s.customer_email WHEN 'phone' THEN s.customer_phone
    WHEN 'address' THEN s.address WHEN 'device' THEN s.device_id
    WHEN 'ip' THEN s.ip_address WHEN 'payment_card' THEN s.payment_token
    WHEN 'refund_account' THEN s.refund_account END, 'sha256'), 'hex')
FROM _batch s
JOIN customers c ON c.external_customer_id = s.customer_id AND c.merchant_id = '$MERCHANT'::uuid
CROSS JOIN (VALUES ('email'),('phone'),('address'),('device'),('ip'),('payment_card'),('refund_account')) AS typ(val)
WHERE CASE typ.val
  WHEN 'email' THEN NULLIF(s.customer_email,'') IS NOT NULL
  WHEN 'phone' THEN NULLIF(s.customer_phone,'') IS NOT NULL
  WHEN 'address' THEN NULLIF(s.address,'') IS NOT NULL
  WHEN 'device' THEN NULLIF(s.device_id,'') IS NOT NULL
  WHEN 'ip' THEN NULLIF(s.ip_address,'') IS NOT NULL
  WHEN 'payment_card' THEN NULLIF(s.payment_token,'') IS NOT NULL
  WHEN 'refund_account' THEN NULLIF(s.refund_account,'') IS NOT NULL END
ON CONFLICT (id) DO NOTHING;

-- 3. Orders
INSERT INTO orders (id, merchant_id, customer_id, external_order_id, sku, product_name, category, product_value, quantity, payment_method, order_date, delivery_date)
SELECT DISTINCT ON (s.order_id, s.customer_id)
  md5('o:' || s.customer_id || ':' || s.order_id)::uuid,
  '$MERCHANT'::uuid, c.id, s.order_id,
  s.sku, s.product_name, s.category,
  NULLIF(s.product_value,'')::numeric,
  GREATEST(1, COALESCE(NULLIF(s.quantity,'')::int, 1)),
  s.payment_method,
  NULLIF(s.order_date,'')::timestamp, NULLIF(s.delivery_date,'')::timestamp
FROM _batch s
JOIN customers c ON c.external_customer_id = s.customer_id AND c.merchant_id = '$MERCHANT'::uuid
WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.external_order_id = s.order_id AND o.customer_id = c.id)
ON CONFLICT (id) DO NOTHING;

-- 4. Shipments
INSERT INTO shipments (id, merchant_id, order_id, carrier, tracking_number_hash, delivery_address_hash, expected_weight, returned_weight, weight_difference)
SELECT DISTINCT ON (s.order_id, s.customer_id)
  md5('sh:' || s.customer_id || ':' || s.order_id)::uuid,
  '$MERCHANT'::uuid, o.id, s.carrier,
  encode(digest(COALESCE(s.tracking_number,''),'sha256'),'hex'),
  encode(digest(COALESCE(s.address,''),'sha256'),'hex'),
  NULLIF(s.expected_weight,'')::numeric, NULLIF(s.returned_weight,'')::numeric,
  (NULLIF(s.expected_weight,'')::numeric - NULLIF(s.returned_weight,'')::numeric)
FROM _batch s
JOIN customers c ON c.external_customer_id = s.customer_id AND c.merchant_id = '$MERCHANT'::uuid
JOIN orders o ON o.external_order_id = s.order_id AND o.customer_id = c.id AND o.merchant_id = '$MERCHANT'::uuid
WHERE NOT EXISTS (SELECT 1 FROM shipments sh WHERE sh.order_id = o.id)
ON CONFLICT (id) DO NOTHING;

-- 5. Return requests
INSERT INTO return_requests (id, merchant_id, customer_id, order_id, shipment_id, return_reason, condition_reported, return_status, return_date, hours_after_delivery)
SELECT DISTINCT ON (s.order_id, s.customer_id)
  md5('r:' || s.customer_id || ':' || s.order_id)::uuid,
  '$MERCHANT'::uuid, c.id, o.id,
  md5('sh:' || s.customer_id || ':' || s.order_id)::uuid,
  s.return_reason, s.return_condition, 'pending',
  NULLIF(s.return_date,'')::timestamp,
  EXTRACT(EPOCH FROM (NULLIF(s.return_date,'')::timestamp - NULLIF(s.delivery_date,'')::timestamp)) / 3600
FROM _batch s
JOIN customers c ON c.external_customer_id = s.customer_id AND c.merchant_id = '$MERCHANT'::uuid
JOIN orders o ON o.external_order_id = s.order_id AND o.customer_id = c.id AND o.merchant_id = '$MERCHANT'::uuid
WHERE NOT EXISTS (SELECT 1 FROM return_requests rr WHERE rr.order_id = o.id)
ON CONFLICT (id) DO NOTHING;

-- 6. Return items
INSERT INTO return_items (id, return_id, order_id, sku, product_name, category, declared_condition)
SELECT
  md5('ri:' || s.customer_id || ':' || s.order_id || ':' || COALESCE(s.sku,''))::uuid,
  rr.id, o.id, s.sku, s.product_name, s.category, s.return_condition
FROM _batch s
JOIN customers c ON c.external_customer_id = s.customer_id AND c.merchant_id = '$MERCHANT'::uuid
JOIN orders o ON o.external_order_id = s.order_id AND o.customer_id = c.id AND o.merchant_id = '$MERCHANT'::uuid
JOIN return_requests rr ON rr.order_id = o.id
ON CONFLICT (id) DO NOTHING;

-- 7. Payments
INSERT INTO payments (id, merchant_id, customer_id, order_id, payment_method, payment_token_hash, amount, chargeback_flag)
SELECT
  md5('p:' || s.customer_id || ':' || s.order_id)::uuid,
  '$MERCHANT'::uuid, c.id, o.id, s.payment_method,
  encode(digest(COALESCE(s.payment_token,''),'sha256'),'hex'),
  NULLIF(s.product_value,'')::numeric,
  COALESCE(NULLIF(s.chargeback,'')::boolean, false)
FROM _batch s
JOIN customers c ON c.external_customer_id = s.customer_id AND c.merchant_id = '$MERCHANT'::uuid
JOIN orders o ON o.external_order_id = s.order_id AND o.customer_id = c.id AND o.merchant_id = '$MERCHANT'::uuid
WHERE (s.payment_method IS NOT NULL AND s.payment_method != '') OR (s.payment_token IS NOT NULL AND s.payment_token != '')
ON CONFLICT (id) DO NOTHING;

-- 8. Refunds
INSERT INTO refunds (id, merchant_id, return_id, customer_id, refund_account_hash, refund_amount, refund_status, refund_date)
SELECT
  md5('rf:' || s.customer_id || ':' || s.order_id)::uuid,
  '$MERCHANT'::uuid, rr.id, c.id,
  encode(digest(s.refund_account,'sha256'),'hex'),
  NULLIF(s.product_value,'')::numeric, 'pending',
  NULLIF(s.return_date,'')::timestamp
FROM _batch s
JOIN customers c ON c.external_customer_id = s.customer_id AND c.merchant_id = '$MERCHANT'::uuid
JOIN orders o ON o.external_order_id = s.order_id AND o.customer_id = c.id AND o.merchant_id = '$MERCHANT'::uuid
JOIN return_requests rr ON rr.order_id = o.id
WHERE NULLIF(s.refund_account,'') IS NOT NULL
ON CONFLICT (id) DO NOTHING;

-- 9. Support interactions
INSERT INTO support_interactions (id, merchant_id, customer_id, return_id, channel, message_text)
SELECT
  md5('su:' || s.customer_id || ':' || s.order_id)::uuid,
  '$MERCHANT'::uuid, c.id, rr.id, 'chat',
  LEFT(s.support_text, 2000)
FROM _batch s
JOIN customers c ON c.external_customer_id = s.customer_id AND c.merchant_id = '$MERCHANT'::uuid
JOIN orders o ON o.external_order_id = s.order_id AND o.customer_id = c.id AND o.merchant_id = '$MERCHANT'::uuid
JOIN return_requests rr ON rr.order_id = o.id
WHERE NULLIF(s.support_text,'') IS NOT NULL
ON CONFLICT (id) DO NOTHING;

INSERT INTO import_jobs (id, source_name, file_name, status, total_rows, processed_rows, failed_rows, started_at, completed_at, error_message, metadata_json)
SELECT
  gen_random_uuid(),
  'sql_load',
  'large_returns_1m.csv',
  'completed',
  COUNT(*),
  COUNT(*),
  0,
  NOW(),
  NOW(),
  NULL,
  jsonb_build_object('batch_offset', $OFFSET, 'batch_size', $BATCH, 'target', 'orders')
FROM _batch;

DROP TABLE IF EXISTS _batch;
SQL

  t1=$(date +%s)
  echo "  Batch done in $((t1 - t0))s"
  OFFSET=$((OFFSET + BATCH))
done

echo "=== DONE ==="
psql_one "SELECT count(*) AS customers FROM customers"
psql_one "SELECT count(*) AS orders FROM orders"
psql_one "SELECT count(*) AS return_requests FROM return_requests"
psql_one "SELECT count(*) AS shipments FROM shipments"
psql_one "SELECT count(*) AS return_items FROM return_items"
psql_one "SELECT count(*) AS payments FROM payments"
psql_one "SELECT count(*) AS refunds FROM refunds"
psql_one "SELECT count(*) AS support_interactions FROM support_interactions"
psql_one "SELECT count(*) AS customer_identities FROM customer_identities"
