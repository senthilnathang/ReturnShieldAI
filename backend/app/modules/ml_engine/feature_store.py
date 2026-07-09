from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

NUMERIC_FEATURES = [
    "product_value",
    "quantity",
    "expected_weight",
    "returned_weight",
    "weight_difference",
    "payment_method_risk_score",
    "account_age_days",
    "lifetime_orders",
    "lifetime_returns",
    "lifetime_refunds",
    "customer_risk_score",
    "hours_after_delivery",
    "customer_return_rate",
    "return_count_30d",
    "return_count_90d",
    "chargeback_count",
    "refund_amount",
    "refund_to_order_value_ratio",
    "same_address_customer_count",
    "same_device_customer_count",
    "same_refund_account_count",
    "same_payment_token_count",
    "support_message_count",
    "return_reason_length",
    "return_reason_word_count",
    "has_empty_box_claim",
    "has_damaged_claim",
    "has_item_not_received_claim",
    "has_urgent_refund_language",
]

CATEGORICAL_FEATURES = [
    "category",
    "payment_method",
    "return_channel",
    "condition_reported",
    "delivery_status",
    "warehouse_scan_status",
    "refund_method",
]

LEAKAGE_COLUMNS = [
    "fraud_score",
    "risk_level",
    "decision",
    "case_status",
    "analyst_decision",
    "confirmed_label",
    "refund_status",
    "closed_at",
    "final_score",
]

TARGET_COLUMN = "is_fraud"
MODEL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

FRAUD_PHRASES = {
    "has_empty_box_claim": ["empty box", "box arrived empty", "empty-package", "empty package"],
    "has_damaged_claim": ["damaged", "broken", "defective", "arrived damaged"],
    "has_item_not_received_claim": ["not received", "never received", "missing item", "item not received"],
    "has_urgent_refund_language": ["refund now", "immediately", "urgent refund", "asap", "right away"],
}


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denom = denominator.replace(0, np.nan)
    return (numerator / denom).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def _ensure_columns(df: pd.DataFrame, columns: Iterable[str], default_value=0.0) -> pd.DataFrame:
    for column in columns:
        if column not in df.columns:
            df[column] = default_value
    return df


def build_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.copy()
    frame.columns = [str(c).lower() for c in frame.columns]

    for column in NUMERIC_FEATURES:
        if column not in frame.columns:
            frame[column] = np.nan
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    for column in CATEGORICAL_FEATURES:
        if column not in frame.columns:
            frame[column] = "unknown"
        frame[column] = frame[column].fillna("unknown").astype(str).str.strip().str.lower().replace({"": "unknown"})

    if "quantity" not in frame.columns:
        frame["quantity"] = 1

    if "expected_weight" not in frame.columns:
        frame["expected_weight"] = np.nan
    if "returned_weight" not in frame.columns:
        frame["returned_weight"] = np.nan
    frame["weight_difference"] = pd.to_numeric(frame.get("weight_difference"), errors="coerce")
    frame["weight_difference"] = frame["weight_difference"].fillna((frame["returned_weight"] - frame["expected_weight"]).abs())

    frame["customer_return_rate"] = safe_divide(frame["lifetime_returns"].fillna(0), frame["lifetime_orders"].fillna(0))
    frame["refund_to_order_value_ratio"] = safe_divide(frame["refund_amount"].fillna(0), frame["product_value"].fillna(0))
    if "return_reason" not in frame.columns:
        frame["return_reason"] = ""
    frame["return_reason"] = frame["return_reason"].fillna("").astype(str)
    reason_lower = frame["return_reason"].str.lower()
    frame["return_reason_length"] = reason_lower.str.len().fillna(0)
    frame["return_reason_word_count"] = reason_lower.str.split().map(len).fillna(0)

    for feature, phrases in FRAUD_PHRASES.items():
        frame[feature] = reason_lower.apply(lambda text: float(any(phrase in text for phrase in phrases)))

    frame = _ensure_columns(frame, ["same_address_customer_count", "same_device_customer_count", "same_refund_account_count", "same_payment_token_count", "support_message_count", "chargeback_count", "return_count_30d", "return_count_90d"], 0.0)

    for column in ["same_address_customer_count", "same_device_customer_count", "same_refund_account_count", "same_payment_token_count", "support_message_count", "chargeback_count", "return_count_30d", "return_count_90d"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)

    if "refund_amount" not in frame.columns:
        frame["refund_amount"] = frame["product_value"].fillna(0)
    frame["refund_amount"] = pd.to_numeric(frame["refund_amount"], errors="coerce").fillna(0.0)

    if TARGET_COLUMN in frame.columns:
        frame[TARGET_COLUMN] = pd.to_numeric(frame[TARGET_COLUMN], errors="coerce").fillna(0).astype(int)

    return frame


def split_features_target(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series | None]:
    frame = build_feature_frame(df)
    target = frame[TARGET_COLUMN] if TARGET_COLUMN in frame.columns else None
    drop_cols = set(LEAKAGE_COLUMNS + [TARGET_COLUMN, "return_id", "merchant_id", "customer_id", "order_id", "shipment_id", "payment_token_hash", "refund_account_hash", "support_message_text", "confirmed_label", "case_status", "analyst_decision"])
    feature_frame = frame.drop(columns=[c for c in drop_cols if c in frame.columns], errors="ignore")
    return feature_frame[MODEL_FEATURES].copy(), target
