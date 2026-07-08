from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

FEATURE_COLUMNS = [
    "product_value",
    "customer_account_age_days",
    "lifetime_orders",
    "lifetime_returns",
    "return_rate_30d",
    "return_rate_90d",
    "customer_return_count_30d",
    "hours_after_delivery",
    "expected_weight",
    "returned_weight",
    "weight_difference",
    "payment_method_risk_score",
    "chargeback_count",
    "address_reuse_count",
    "same_device_account_count",
    "previous_fraud_count",
]

def _to_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)

def _hours_after_delivery(delivery_date: datetime, return_date: datetime) -> float:
    delta = _to_utc_naive(return_date) - _to_utc_naive(delivery_date)
    return round(max(delta.total_seconds() / 3600.0, 0.0), 2)

def build_features(customer: Any, order: Any, return_record: Any, stats: dict[str, Any]) -> dict[str, float]:
    return_rate_30d = stats.get("return_rate_30d")
    if return_rate_30d is None:
        orders_30d = max(stats.get("orders_30d", 0), 1)
        return_rate_30d = stats.get("customer_return_count_30d", 0) / orders_30d

    features = {
        "product_value": float(order.product_value),
        "customer_account_age_days": float(customer.account_age_days),
        "lifetime_orders": float(customer.lifetime_orders),
        "lifetime_returns": float(customer.lifetime_returns),
        "return_rate_30d": float(return_rate_30d),
        "return_rate_90d": float(stats.get("return_rate_90d", return_rate_30d)),
        "customer_return_count_30d": float(stats.get("customer_return_count_30d", customer.lifetime_returns)),
        "hours_after_delivery": float(_hours_after_delivery(order.delivery_date, return_record.return_date)),
        "expected_weight": float(order.expected_weight),
        "returned_weight": float(return_record.returned_weight),
        "weight_difference": abs(float(order.expected_weight) - float(return_record.returned_weight)),
        "payment_method_risk_score": float(order.payment_method_risk_score),
        "chargeback_count": float(stats.get("chargeback_count", 0)),
        "address_reuse_count": float(stats.get("address_reuse_count", 0)),
        "same_device_account_count": float(stats.get("same_device_account_count", 0)),
        "previous_fraud_count": float(stats.get("previous_fraud_count", 0)),
    }
    return features

def text_features(text: str) -> dict[str, float | bool]:
    lowered = text.lower()
    patterns = {
        "text_empty_box_flag": any(token in lowered for token in ["empty box", "box was empty", "nothing inside", "missing item"]),
        "text_item_not_received_flag": any(token in lowered for token in ["item not received", "never received", "did not receive"]),
        "text_chargeback_threat_flag": any(token in lowered for token in ["chargeback", "credit card dispute", "refund or chargeback"]),
        "text_damaged_claim_flag": any(token in lowered for token in ["damaged", "broken", "defective", "arrived damaged"]),
        "text_generic_script_flag": len(lowered.split()) < 18 or "same issue" in lowered,
    }
    return patterns
