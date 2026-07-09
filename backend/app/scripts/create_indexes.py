#!/usr/bin/env python3
"""
Create additional indexes for query optimization.

Run after initial migration or after large data imports.

Usage:
    python scripts/create_indexes.py
"""

import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.core.database import sync_engine
from app.core.logging import setup_logging
from sqlalchemy import text

logger = logging.getLogger("returnshield.scripts.create_indexes")

INDEXES = [
    # Composite indexes for dashboard filters
    "CREATE INDEX IF NOT EXISTS idx_fraud_scores_merchant_risk ON fraud_scores (merchant_id, risk_level, created_at DESC);",
    "CREATE INDEX IF NOT EXISTS idx_fraud_cases_merchant_status ON fraud_cases (merchant_id, case_status, created_at DESC);",
    "CREATE INDEX IF NOT EXISTS idx_return_requests_merchant_status ON return_requests (merchant_id, return_status, created_at DESC);",

    # BRIN indexes for large timestamp tables
    "CREATE INDEX IF NOT EXISTS idx_return_requests_created_brin ON return_requests USING BRIN (created_at);",
    "CREATE INDEX IF NOT EXISTS idx_fraud_scores_created_brin ON fraud_scores USING BRIN (created_at);",
    "CREATE INDEX IF NOT EXISTS idx_fraud_cases_created_brin ON fraud_cases USING BRIN (created_at);",

    # GIN indexes for JSONB
    "CREATE INDEX IF NOT EXISTS idx_fraud_scores_reason_codes_gin ON fraud_scores USING GIN (reason_codes_json);",
    "CREATE INDEX IF NOT EXISTS idx_fraud_scores_breakdown_gin ON fraud_scores USING GIN (score_breakdown_json);",
    "CREATE INDEX IF NOT EXISTS idx_merchants_settings_gin ON merchants USING GIN (settings_json);",

    # Full-text search indexes
    "CREATE INDEX IF NOT EXISTS idx_return_requests_reason_fts ON return_requests USING GIN (to_tsvector('english', COALESCE(return_reason, '')));",
    "CREATE INDEX IF NOT EXISTS idx_support_text_fts ON support_interactions USING GIN (to_tsvector('english', COALESCE(message_text, '')));",

    # Identity & fraud ring indexes
    "CREATE INDEX IF NOT EXISTS idx_customer_identities_lookup ON customer_identities (merchant_id, identity_type, identity_value_hash);",
    "CREATE INDEX IF NOT EXISTS idx_customer_identities_customer ON customer_identities (customer_id);",

    # Payment & refund graph indexes
    "CREATE INDEX IF NOT EXISTS idx_payments_token ON payments (payment_token_hash);",
    "CREATE INDEX IF NOT EXISTS idx_refunds_account ON refunds (refund_account_hash);",
    "CREATE INDEX IF NOT EXISTS idx_payments_upi ON payments (upi_hash);",

    # Order/indexes for product-level fraud analytics
    "CREATE INDEX IF NOT EXISTS idx_orders_category_value ON orders (category, product_value DESC);",
    "CREATE INDEX IF NOT EXISTS idx_orders_sku ON orders (sku, merchant_id);",

    # Shipment weight difference index
    "CREATE INDEX IF NOT EXISTS idx_shipments_weight_diff ON shipments (weight_difference DESC NULLS LAST);",

    # Customer risk index
    "CREATE INDEX IF NOT EXISTS idx_customers_risk_score ON customers (merchant_id, customer_risk_score DESC);",
]


def main():
    setup_logging()
    logger.info("Creating %d indexes...", len(INDEXES))

    with sync_engine.connect() as conn:
        for idx_sql in INDEXES:
            try:
                conn.execute(text(idx_sql))
                logger.debug("Created: %s", idx_sql[:60])
            except Exception as e:
                logger.warning("Index creation skipped: %s", str(e)[:100])
        conn.commit()

    logger.info("Index creation complete")


if __name__ == "__main__":
    main()
