"""
Single-pass loader: reads staging sequentially, bulk-inserts into all tables.
Run after staging has 1M rows (takes ~36s via COPY).

Usage: python -m app.scripts.staging_transform
"""

import hashlib
import logging
import os
import sys
import time
from uuid import uuid4

from psycopg2 import connect
from psycopg2.extras import execute_values, register_uuid

register_uuid()
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
log = logging.getLogger("xfrm")

MERCHANT = "f17cc48d-8a76-4d63-b07a-b2aaacc7afe5"
BATCH = 5000  # rows per bulk insert


def _h(v):
    if not v or v.strip() == "":
        return None
    return hashlib.sha256(v.strip().lower().encode()).hexdigest()


def _f(v):
    if not v or v.strip() == "":
        return None
    try:
        return float(v.replace("$", "").replace(",", ""))
    except (ValueError, TypeError):
        return None


def _dt(v):
    if not v or v.strip() == "":
        return None
    try:
        from datetime import datetime
        return datetime.fromisoformat(v)
    except (ValueError, TypeError):
        return None


def _hours(rt, dl):
    if rt and dl:
        d = rt - dl
        return max(0, d.total_seconds() / 3600)
    return None


def main():
    db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL", "")
    db_url = db_url.replace("+asyncpg", "").replace("+psycopg2", "")
    log.info("Connecting: %s", db_url)
    conn = connect(db_url)
    conn.autocommit = False
    cur = conn.cursor()

    # Verify staging has data
    cur.execute("SELECT count(*) FROM staging")
    stag_count = cur.fetchone()[0]
    log.info("Staging rows: %s", f"{stag_count:,}")

    t_start = time.time()
    total = 0
    # Per-table buffers
    buf = {k: [] for k in ("customers", "idents", "orders", "shipments",
                           "returns", "ritems", "payments", "refunds", "supports")}
    seen_customers = {}
    seen_orders = {}
    seen_shipments = {}
    seen_returns = {}

    cur.execute("DECLARE c CURSOR WITH HOLD FOR SELECT * FROM staging")
    while True:
        cur.execute("FETCH FORWARD 5000 FROM c")
        rows = cur.fetchall()
        if not rows:
            break

        for r in rows:
            (cid, cname, cemail, cphone, oid, odate, sku, pname, cat,
             pval, qty, pm, reason, rdate, ddate, ew, rw,
             carrier, tn, addr, dev, ip, ptok, racc, rcond, chbk, stxt) = r

            cst_id = seen_customers.get(cid)
            if not cst_id:
                cst_id = uuid4()
                seen_customers[cid] = cst_id
                buf["customers"].append((
                    cst_id, MERCHANT, cid, cname,
                    _h(cemail), _h(cphone),
                ))

            # Identities
            for typ, val in [("email", _h(cemail)), ("phone", _h(cphone)),
                             ("address", _h(addr)), ("device", _h(dev)),
                             ("ip", _h(ip)), ("payment_card", _h(ptok)),
                             ("refund_account", _h(racc))]:
                if val:
                    buf["idents"].append((uuid4(), cst_id, MERCHANT, typ, val))

            oid_key = (cid, oid)
            ord_id = seen_orders.get(oid_key)
            if not ord_id:
                ord_id = uuid4()
                seen_orders[oid_key] = ord_id
                buf["orders"].append((
                    ord_id, MERCHANT, cst_id, oid, sku, pname, cat,
                    _f(pval), int(float(qty or "1")), pm,
                    _dt(odate), _dt(ddate),
                ))

            shp_id = seen_shipments.get(oid_key)
            if not shp_id:
                shp_id = uuid4()
                seen_shipments[oid_key] = shp_id
                ew_f = _f(ew)
                rw_f = _f(rw)
                buf["shipments"].append((
                    shp_id, MERCHANT, ord_id, carrier,
                    _h(tn), _h(addr), ew_f, rw_f,
                    (ew_f - rw_f) if ew_f is not None and rw_f is not None else None,
                ))

            ret_id = seen_returns.get(oid_key)
            if not ret_id:
                ret_id = uuid4()
                seen_returns[oid_key] = ret_id
                rt = _dt(rdate)
                dl = _dt(ddate)
                buf["returns"].append((
                    ret_id, MERCHANT, cst_id, ord_id, shp_id,
                    reason, rcond, "pending", rt, _hours(rt, dl),
                ))

            buf["ritems"].append((
                uuid4(), ret_id, ord_id, sku, pname, cat, rcond,
            ))

            if pm or ptok:
                buf["payments"].append((
                    uuid4(), MERCHANT, cst_id, ord_id, pm,
                    _h(ptok), _f(pval), bool(chbk),
                ))

            if racc:
                buf["refunds"].append((
                    uuid4(), MERCHANT, ret_id, cst_id,
                    _h(racc), _f(pval), "pending", _dt(rdate),
                ))

            if stxt:
                buf["supports"].append((
                    uuid4(), MERCHANT, cst_id, ret_id, "chat", stxt[:2000],
                ))

            total += 1
            if total % 5000 == 0:
                log.info("  Processed: %s rows", f"{total:,}")

        # Flush every 5K, commit every 50K
        if total > 0 and total % 5000 == 0:
            _flush_all(cur, buf)
        if total > 0 and total % 50000 == 0:
            conn.commit()

    # Final flush + commit
    _flush_all(cur, buf)
    conn.commit()
    cur.close()
    conn.close()
    elapsed = time.time() - t_start
    log.info("=" * 60)
    log.info("DONE: %s rows in %.1fs (%.0f rows/sec)",
             f"{total:,}", elapsed, total / elapsed if elapsed else 0)


def _flush_all(cur, buf):
    order = ["customers","idents","orders","shipments","returns",
             "ritems","payments","refunds","supports"]
    for tbl in order:
        if buf[tbl]:
            _flush(cur, tbl, buf[tbl])
            buf[tbl] = []


def _flush(cur, tbl, data):
    sqls = {
        "customers": "INSERT INTO customers (id,merchant_id,external_customer_id,name,email_hash,phone_hash) VALUES %s ON CONFLICT DO NOTHING",
        "idents": "INSERT INTO customer_identities (id,customer_id,merchant_id,identity_type,identity_value_hash) VALUES %s",
        "orders": "INSERT INTO orders (id,merchant_id,customer_id,external_order_id,sku,product_name,category,product_value,quantity,payment_method,order_date,delivery_date) VALUES %s",
        "shipments": "INSERT INTO shipments (id,merchant_id,order_id,carrier,tracking_number_hash,delivery_address_hash,expected_weight,returned_weight,weight_difference) VALUES %s",
        "returns": "INSERT INTO return_requests (id,merchant_id,customer_id,order_id,shipment_id,return_reason,condition_reported,return_status,return_date,hours_after_delivery) VALUES %s",
        "ritems": "INSERT INTO return_items (id,return_id,order_id,sku,product_name,category,declared_condition) VALUES %s",
        "payments": "INSERT INTO payments (id,merchant_id,customer_id,order_id,payment_method,payment_token_hash,amount,chargeback_flag) VALUES %s",
        "refunds": "INSERT INTO refunds (id,merchant_id,return_id,customer_id,refund_account_hash,refund_amount,refund_status,refund_date) VALUES %s",
        "supports": "INSERT INTO support_interactions (id,merchant_id,customer_id,return_id,channel,message_text) VALUES %s",
    }
    execute_values(cur, sqls[tbl], data, page_size=5000)


if __name__ == "__main__":
    main()
