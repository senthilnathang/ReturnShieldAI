from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
from sklearn.linear_model import LogisticRegression

from backend.app.modules.ml_engine import model_registry
from backend.app.modules.ml_engine.preprocessing import build_preprocessor


def test_model_registry_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(model_registry, "ml_config", SimpleNamespace(artifact_root=tmp_path, best_model_dir=tmp_path / "best_model"))

    frame = pd.DataFrame(
        [
            {"product_value": 100, "quantity": 1, "expected_weight": 1.0, "returned_weight": 1.0, "weight_difference": 0.0, "payment_method_risk_score": 10, "account_age_days": 120, "lifetime_orders": 10, "lifetime_returns": 1, "lifetime_refunds": 0, "customer_risk_score": 10, "hours_after_delivery": 72, "customer_return_rate": 0.1, "return_count_30d": 1, "return_count_90d": 1, "chargeback_count": 0, "refund_amount": 100, "refund_to_order_value_ratio": 1.0, "same_address_customer_count": 1, "same_device_customer_count": 1, "same_refund_account_count": 0, "same_payment_token_count": 0, "support_message_count": 0, "return_reason_length": 12, "return_reason_word_count": 2, "has_empty_box_claim": 0, "has_damaged_claim": 0, "has_item_not_received_claim": 0, "has_urgent_refund_language": 0, "category": "apparel", "payment_method": "card", "return_channel": "web", "condition_reported": "new", "delivery_status": "delivered", "warehouse_scan_status": "ok", "refund_method": "card"},
            {"product_value": 300, "quantity": 1, "expected_weight": 1.0, "returned_weight": 0.1, "weight_difference": 0.9, "payment_method_risk_score": 70, "account_age_days": 10, "lifetime_orders": 2, "lifetime_returns": 2, "lifetime_refunds": 30, "customer_risk_score": 60, "hours_after_delivery": 12, "customer_return_rate": 1.0, "return_count_30d": 5, "return_count_90d": 7, "chargeback_count": 2, "refund_amount": 300, "refund_to_order_value_ratio": 1.0, "same_address_customer_count": 3, "same_device_customer_count": 3, "same_refund_account_count": 2, "same_payment_token_count": 2, "support_message_count": 3, "return_reason_length": 28, "return_reason_word_count": 5, "has_empty_box_claim": 1, "has_damaged_claim": 1, "has_item_not_received_claim": 0, "has_urgent_refund_language": 1, "category": "electronics", "payment_method": "card", "return_channel": "chat", "condition_reported": "used", "delivery_status": "delivered", "warehouse_scan_status": "mismatch", "refund_method": "bank"},
        ]
    )
    y = [0, 1]
    preprocessor = build_preprocessor("logistic_regression")
    X = preprocessor.fit_transform(frame)
    model = LogisticRegression(max_iter=1000).fit(X, y)

    metadata = {
        "version": "2026-07-09-001",
        "model_type": "logistic_regression",
        "artifact_format": "pkl",
        "feature_importance": [{"feature": "weight_difference", "importance": 0.9}],
        "preprocessor_features": list(preprocessor.get_feature_names_out()),
        "metrics": {"pr_auc": 0.9},
    }
    info = model_registry.save_model(model, preprocessor, metadata, "logistic_regression", metrics=metadata["metrics"])
    loaded = model_registry.load_model("logistic_regression", info.version)
    assert loaded["metadata"]["version"] == info.version
    assert loaded["artifact_path"].endswith("model.pkl")

    promoted = model_registry.promote_model_to_best("logistic_regression", info.version)
    assert promoted["metadata"]["best_model_type"] == "logistic_regression"
