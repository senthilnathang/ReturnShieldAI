from __future__ import annotations

import pandas as pd

from backend.app.modules.ml_engine.feature_store import build_feature_frame, MODEL_FEATURES


def test_build_feature_frame_derives_flags_and_ratios():
    frame = pd.DataFrame(
        [
            {
                "product_value": 200,
                "quantity": 1,
                "expected_weight": 1.2,
                "returned_weight": 0.2,
                "payment_method_risk_score": 40,
                "account_age_days": 15,
                "lifetime_orders": 4,
                "lifetime_returns": 2,
                "lifetime_refunds": 10,
                "customer_risk_score": 55,
                "hours_after_delivery": 24,
                "return_count_30d": 3,
                "return_count_90d": 5,
                "chargeback_count": 1,
                "refund_amount": 50,
                "same_address_customer_count": 2,
                "same_device_customer_count": 1,
                "same_refund_account_count": 0,
                "same_payment_token_count": 1,
                "support_message_count": 1,
                "category": "apparel",
                "payment_method": "card",
                "return_channel": "web",
                "condition_reported": "used",
                "delivery_status": "delivered",
                "warehouse_scan_status": "mismatch",
                "refund_method": "card",
                "return_reason": "Empty box please refund now",
            }
        ]
    )

    result = build_feature_frame(frame)
    assert set(MODEL_FEATURES).issubset(result.columns)
    assert result.loc[0, "has_empty_box_claim"] == 1.0
    assert result.loc[0, "has_urgent_refund_language"] == 1.0
    assert result.loc[0, "refund_to_order_value_ratio"] == 0.25
    assert result.loc[0, "weight_difference"] == 1.0
