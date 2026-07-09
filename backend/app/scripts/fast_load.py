"""
Fast CSV loader for 1M+ records using psycopg2 bulk COPY.

Usage:
  python -m app.scripts.fast_load --file /tmp/large_returns_1m.csv

Uses psycopg2.extras.execute_values for batch inserts (10-50x faster
than SQLAlchemy ORM row-by-row). Requires DATABASE_URL_SYNC env var
(postgresql://user:pass@host:port/db).

Process:
  1. Read CSV in large chunks (default 50K)
  2. Vectorize hash + parse operations
  3. Bulk INSERT each model type per chunk
  4. Commit per chunk
"""

import argparse
import hashlib
import logging
import os
import sys
import time
from uuid import uuid4

import pandas as pd
from psycopg2 import connect
from psycopg2.extras import execute_values
from psycopg2.extras import register_uuid as _reg_uuid
_reg_uuid()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("fast_load")


def _hash(val: str | None) -> str | None:
    if not val or val.strip() == "":
        return None
    return hashlib.sha256(val.strip().lower().encode("utf-8")).hexdigest()


def _safe_float(val: str | None) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(str(val).replace("$", "").replace(",", ""))
    except (ValueError, TypeError):
        return None


def _safe_dt(val: str | None):
    if val is None or val == "":
        return None
    try:
        from datetime import datetime
        return datetime.fromisoformat(val)
    except (ValueError, TypeError):
        return None


MERCHANT_ID = None  # resolved once on connect
CHUNK_SIZE = 50_000
CSV_PATH = None


def resolve_merchant(cur):
    global MERCHANT_ID
    cur.execute("SELECT id FROM merchants LIMIT 1")
    row = cur.fetchone()
    if row:
        MERCHANT_ID = row[0]
        logger.info("Using existing merchant: %s", MERCHANT_ID)
    else:
        from uuid import uuid4
        MERCHANT_ID = uuid4()
        cur.execute(
            "INSERT INTO merchants (id, name, industry) VALUES (%s, %s, %s)",
            (MERCHANT_ID, "Demo Merchant", "e-commerce"),
        )
        logger.info("Created demo merchant: %s", MERCHANT_ID)


def load_chunk(chunk: pd.DataFrame, cur):
    """Process one chunk and bulk-insert all models."""
    n = len(chunk)
    t0 = time.time()

    # Pre-allocate lists for each model
    customers = []
    identities = []
    orders = []
    shipments = []
    return_reqs = []
    return_items = []
    payments = []
    refunds = []
    supports = []

    for _, row in chunk.iterrows():
        customer_id = uuid4()
        email_hash = _hash(row.get("customer_email"))
        phone_hash = _hash(row.get("customer_phone"))

        customers.append((
            customer_id, MERCHANT_ID,
            row.get("customer_id"), row.get("customer_name"),
            email_hash, phone_hash,
        ))

        for id_type, val in [
            ("email", email_hash),
            ("phone", phone_hash),
            ("address", _hash(row.get("address"))),
            ("device", _hash(row.get("device_id"))),
            ("ip", _hash(row.get("ip_address"))),
            ("payment_card", _hash(row.get("payment_token"))),
            ("refund_account", _hash(row.get("refund_account"))),
        ]:
            if val:
                identities.append((uuid4(), customer_id, MERCHANT_ID, id_type, val))

        order_id = uuid4()
        orders.append((
            order_id, MERCHANT_ID, customer_id,
            row.get("order_id"), row.get("sku"),
            row.get("product_name"), row.get("category"),
            _safe_float(row.get("product_value")),
            int(float(row.get("quantity", "1"))),
            row.get("payment_method"),
            _safe_dt(row.get("order_date")),
            _safe_dt(row.get("delivery_date")),
        ))

        shipment_id = uuid4()
        exp_w = _safe_float(row.get("expected_weight"))
        ret_w = _safe_float(row.get("returned_weight"))
        w_diff = (exp_w - ret_w) if exp_w is not None and ret_w is not None else None
        shipments.append((
            shipment_id, MERCHANT_ID, order_id,
            row.get("carrier"),
            _hash(row.get("tracking_number")),
            _hash(row.get("address")),
            exp_w, ret_w, w_diff,
        ))

        return_req_id = uuid4()
        rt_date = _safe_dt(row.get("return_date"))
        dl_date = _safe_dt(row.get("delivery_date"))
        hrs = (max(0, (rt_date - dl_date).total_seconds() / 3600)
               if rt_date and dl_date else None)
        return_reqs.append((
            return_req_id, MERCHANT_ID, customer_id, order_id, shipment_id,
            row.get("return_reason"), row.get("return_condition"),
            "pending", rt_date, hrs,
        ))

        return_items.append((
            uuid4(), return_req_id, order_id,
            row.get("sku"), row.get("product_name"),
            row.get("category"), row.get("return_condition"),
        ))

        if row.get("payment_method") or row.get("payment_token"):
            payments.append((
                uuid4(), MERCHANT_ID, customer_id, order_id,
                row.get("payment_method"),
                _hash(row.get("payment_token")),
                _safe_float(row.get("product_value")),
                bool(row.get("chargeback")),
            ))

        if row.get("refund_account"):
            refunds.append((
                uuid4(), MERCHANT_ID, return_req_id, customer_id,
                _hash(row.get("refund_account")),
                _safe_float(row.get("product_value")),
                "pending", rt_date,
            ))

        if row.get("support_text"):
            supports.append((
                uuid4(), MERCHANT_ID, customer_id, return_req_id,
                "chat", row.get("support_text"),
            ))

    t1 = time.time()

    # Bulk inserts using execute_values
    if customers:
        execute_values(cur,
            "INSERT INTO customers (id, merchant_id, external_customer_id, name, email_hash, phone_hash) VALUES %s",
            customers, page_size=5000)
    if identities:
        execute_values(cur,
            "INSERT INTO customer_identities (id, customer_id, merchant_id, identity_type, identity_value_hash) VALUES %s",
            identities, page_size=5000)
    if orders:
        execute_values(cur,
            "INSERT INTO orders (id, merchant_id, customer_id, external_order_id, sku, product_name, category, product_value, quantity, payment_method, order_date, delivery_date) VALUES %s",
            orders, page_size=5000)
    if shipments:
        execute_values(cur,
            "INSERT INTO shipments (id, merchant_id, order_id, carrier, tracking_number_hash, delivery_address_hash, expected_weight, returned_weight, weight_difference) VALUES %s",
            shipments, page_size=5000)
    if return_reqs:
        execute_values(cur,
            "INSERT INTO return_requests (id, merchant_id, customer_id, order_id, shipment_id, return_reason, condition_reported, return_status, return_date, hours_after_delivery) VALUES %s",
            return_reqs, page_size=5000)
    if return_items:
        execute_values(cur,
            "INSERT INTO return_items (id, return_id, order_id, sku, product_name, category, declared_condition) VALUES %s",
            return_items, page_size=5000)
    if payments:
        execute_values(cur,
            "INSERT INTO payments (id, merchant_id, customer_id, order_id, payment_method, payment_token_hash, amount, chargeback_flag) VALUES %s",
            payments, page_size=5000)
    if refunds:
        execute_values(cur,
            "INSERT INTO refunds (id, merchant_id, return_id, customer_id, refund_account_hash, refund_amount, refund_status, refund_date) VALUES %s",
            refunds, page_size=5000)
    if supports:
        execute_values(cur,
            "INSERT INTO support_interactions (id, merchant_id, customer_id, return_id, channel, message_text) VALUES %s",
            supports, page_size=5000)

    t2 = time.time()
    logger.info("  Chunk %d rows: build=%.1fs insert=%.1fs",
                n, t1 - t0, t2 - t1)


def main():
    global CSV_PATH, CHUNK_SIZE

    parser = argparse.ArgumentParser(description="Fast CSV loader for ReturnShieldAI")
    parser.add_argument("--file", required=True, help="Path to CSV file")
    parser.add_argument("--chunk-size", type=int, default=50_000, help="Rows per chunk")
    parser.add_argument("--env-file", default=None, help="Path to .env file with DATABASE_URL_SYNC")
    args = parser.parse_args()

    CSV_PATH = args.file
    CHUNK_SIZE = args.chunk_size

    # Load env file if provided
    if args.env_file:
        with open(args.env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

    db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL", "")
    db_url = db_url.replace("+asyncpg", "").replace("+psycopg2", "")
    if not db_url:
        logger.error("DATABASE_URL_SYNC not set.")
        sys.exit(1)

    logger.info("Connecting: %s", db_url.replace(db_url.split("@")[0].split("://")[1], "***:***") if "@" in db_url else db_url)
    logger.info("File: %s", CSV_PATH)
    logger.info("Chunk size: %s rows", f"{CHUNK_SIZE:,}")

    conn = connect(db_url)
    cur = conn.cursor()
    resolve_merchant(cur)
    conn.commit()

    total_rows = 0
    t_start = time.time()

    for chunk in pd.read_csv(CSV_PATH, chunksize=CHUNK_SIZE, dtype=str, keep_default_na=False):
        chunk = chunk.replace({float("nan"): None, "": None})
        total_rows += len(chunk)
        load_chunk(chunk, cur)
        conn.commit()
        logger.info("  Committed. Total: %s rows, elapsed: %.1fs",
                     f"{total_rows:,}", time.time() - t_start)

    cur.close()
    conn.close()
    elapsed = time.time() - t_start
    logger.info("=" * 60)
    logger.info("DONE: %s rows in %.1fs (%.0f rows/sec)",
                f"{total_rows:,}", elapsed, total_rows / elapsed if elapsed > 0 else 0)


if __name__ == "__main__":
    main()
