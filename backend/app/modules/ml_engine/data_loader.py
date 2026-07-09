from __future__ import annotations

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .config import ml_config


class MLDataLoader:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _query(self, return_filter: str = "", merchant_filter: str = "", limit_sql: str = ""):
        return text(
            f"""
            WITH identity_pivot AS (
                SELECT
                    customer_id,
                    MAX(CASE WHEN identity_type = 'address' THEN identity_value_hash END) AS address_hash,
                    MAX(CASE WHEN identity_type = 'device' THEN identity_value_hash END) AS device_hash
                FROM customer_identities
                GROUP BY customer_id
            ),
            address_counts AS (
                SELECT identity_value_hash, COUNT(DISTINCT customer_id) AS same_address_customer_count
                FROM customer_identities
                WHERE identity_type = 'address'
                GROUP BY identity_value_hash
            ),
            device_counts AS (
                SELECT identity_value_hash, COUNT(DISTINCT customer_id) AS same_device_customer_count
                FROM customer_identities
                WHERE identity_type = 'device'
                GROUP BY identity_value_hash
            ),
            payment_counts AS (
                SELECT payment_token_hash, COUNT(*) AS same_payment_token_count
                FROM payments
                WHERE payment_token_hash IS NOT NULL
                GROUP BY payment_token_hash
            ),
            refund_counts AS (
                SELECT refund_account_hash, COUNT(*) AS same_refund_account_count
                FROM refunds
                WHERE refund_account_hash IS NOT NULL
                GROUP BY refund_account_hash
            ),
            support_counts AS (
                SELECT return_id, COUNT(*) AS support_message_count
                FROM support_interactions
                GROUP BY return_id
            ),
            customer_stats AS (
                SELECT
                    r.customer_id,
                    COUNT(*) FILTER (WHERE r.created_at >= NOW() - INTERVAL '30 days') AS return_count_30d,
                    COUNT(*) FILTER (WHERE r.created_at >= NOW() - INTERVAL '90 days') AS return_count_90d,
                    COALESCE((
                        SELECT COUNT(*)
                        FROM payments p2
                        WHERE p2.customer_id = r.customer_id AND p2.chargeback_flag = TRUE
                    ), 0) AS chargeback_count
                FROM return_requests r
                GROUP BY r.customer_id
            )
            SELECT
                r.id AS return_id,
                r.merchant_id,
                r.customer_id,
                r.order_id,
                r.shipment_id,
                r.external_return_id,
                r.return_reason,
                r.condition_reported,
                r.return_status,
                r.return_channel,
                r.return_date,
                r.hours_after_delivery,
                r.created_at AS return_created_at,
                c.name AS customer_name,
                c.account_age_days,
                c.lifetime_orders,
                c.lifetime_returns,
                c.lifetime_refunds,
                c.customer_risk_score,
                o.product_value,
                o.quantity,
                o.payment_method,
                o.payment_method_risk_score,
                o.category,
                o.order_date,
                o.delivery_date,
                s.expected_weight,
                s.returned_weight,
                s.weight_difference,
                s.delivery_status,
                s.warehouse_scan_status,
                p.payment_token_hash,
                p.payment_method AS payment_method_payment,
                p.amount AS payment_amount,
                p.chargeback_flag,
                rf.refund_method,
                rf.refund_account_hash,
                rf.refund_amount,
                rf.refund_status,
                sc.support_message_count,
                cs.return_count_30d,
                cs.return_count_90d,
                cs.chargeback_count,
                ac.same_address_customer_count,
                dc.same_device_customer_count,
                pc.same_payment_token_count,
                rc.same_refund_account_count,
                ip.address_hash,
                ip.device_hash,
                fb.confirmed_label,
                fc.case_status,
                (
                    SELECT si.message_text
                    FROM support_interactions si
                    WHERE si.return_id = r.id
                    ORDER BY si.created_at DESC
                    LIMIT 1
                ) AS support_message_text,
                CASE
                    WHEN LOWER(COALESCE(fb.confirmed_label, '')) IN ('confirmed_fraud', 'fraud', 'true', 'yes') THEN 1
                    WHEN LOWER(COALESCE(fc.case_status, '')) IN ('confirmed_fraud', 'fraud', 'confirmed') THEN 1
                    WHEN COALESCE(p.chargeback_flag, FALSE) = TRUE THEN 1
                    ELSE 0
                END AS is_fraud
            FROM return_requests r
            JOIN customers c ON c.id = r.customer_id
            JOIN orders o ON o.id = r.order_id
            LEFT JOIN shipments s ON s.id = r.shipment_id
            LEFT JOIN payments p ON p.order_id = r.order_id
            LEFT JOIN refunds rf ON rf.return_id = r.id
            LEFT JOIN support_counts sc ON sc.return_id = r.id
            LEFT JOIN customer_stats cs ON cs.customer_id = r.customer_id
            LEFT JOIN identity_pivot ip ON ip.customer_id = r.customer_id
            LEFT JOIN address_counts ac ON ac.identity_value_hash = ip.address_hash
            LEFT JOIN device_counts dc ON dc.identity_value_hash = ip.device_hash
            LEFT JOIN payment_counts pc ON pc.payment_token_hash = p.payment_token_hash
            LEFT JOIN refund_counts rc ON rc.refund_account_hash = rf.refund_account_hash
            LEFT JOIN analyst_feedback fb ON fb.return_id = r.id
            LEFT JOIN fraud_cases fc ON fc.return_id = r.id
            {merchant_filter}
            {return_filter}
            ORDER BY r.created_at DESC
            {limit_sql}
            """
        )

    async def load_training_frame(self, merchant_id=None, limit: int | None = None) -> pd.DataFrame:
        params = {}
        merchant_filter = ""
        limit_sql = ""
        if merchant_id is not None:
            merchant_filter = "WHERE r.merchant_id = :merchant_id"
            params["merchant_id"] = str(merchant_id)
        if limit:
            limit_sql = "LIMIT :limit"
            params["limit"] = int(limit)

        result = await self.session.execute(self._query(merchant_filter=merchant_filter, limit_sql=limit_sql), params)
        return pd.DataFrame(result.mappings().all())

    async def load_prediction_frame(self, return_id) -> pd.DataFrame:
        result = await self.session.execute(self._query(return_filter="WHERE r.id = :return_id", limit_sql="LIMIT 1"), {"return_id": str(return_id)})
        return pd.DataFrame(result.mappings().all())
