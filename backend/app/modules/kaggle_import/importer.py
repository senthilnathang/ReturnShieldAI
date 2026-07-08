from __future__ import annotations

import json
import os
import random
import tempfile
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd

from backend.app.db.session import Session
from backend.app.models import (
    Customer,
    FraudScore,
    Order,
    ReturnCase,
    ReturnRecord,
    Rule,
)

COLUMN_MAP = {
    "customer_id": "customer_id",
    "order_id": "order_id",
    "transaction_date": "transaction_date",
    "product": "product_name",
    "industry": "category",
    "unit_price_usd": "product_value",
    "quantity": "quantity",
    "payment_method": "payment_method",
    "order_status": "order_status",
    "return_flag": "return_flag",
    "support_tickets": "support_tickets",
    "days_to_delivery": "days_to_delivery",
    "customer_tenure_days": "account_age_days",
    "is_repeat_customer": "is_repeat_customer",
    "frequency_orders": "frequency_orders",
    "monetary_total_usd": "monetary_total_usd",
    "avg_order_value_usd": "avg_order_value_usd",
    "shipping_cost_usd": "shipping_cost_usd",
    "discount_pct": "discount_pct",
    "country": "country",
}

REQUIRED_SOURCE_COLUMNS = [
    "customer_id", "order_id", "transaction_date", "product",
    "unit_price_usd", "order_status", "return_flag",
]


def find_dataset_files(dataset_path: str) -> list[str]:
    files = []
    for root, _dirs, fnames in os.walk(dataset_path):
        for f in fnames:
            if f.endswith(".csv") or f.endswith(".parquet"):
                files.append(os.path.join(root, f))
    return sorted(files)


def validate_schema(df: pd.DataFrame) -> list[str]:
    missing = [col for col in REQUIRED_SOURCE_COLUMNS if col not in df.columns]
    return missing


def map_customer(df_row: dict[str, Any], idx: int) -> dict[str, Any]:
    cid = str(df_row.get("customer_id", f"kaggle-{idx}"))
    tenure = int(df_row.get("customer_tenure_days", 0) or 0)
    freq_orders = int(df_row.get("frequency_orders", 0) or 0)
    monetary = float(df_row.get("monetary_total_usd", 0) or 0)
    avg_order = float(df_row.get("avg_order_value_usd", 0) or 0)
    name = f"K-User-{str(cid)[:8]}"

    return {
        "name": name,
        "email": f"{name.lower()}@kaggle-import.local",
        "phone": f"+1-555-{1000 + (idx % 9000):04d}",
        "account_age_days": max(1, tenure),
        "lifetime_orders": max(0, freq_orders),
        "lifetime_returns": max(0, int(random.gauss(freq_orders * 0.15, 2))),
        "address": f"{100 + idx} Kaggle Ave, {df_row.get('country', 'Unknown')}",
        "device_id": f"kaggle-device-{idx % 100:03d}",
    }


def map_order(df_row: dict[str, Any], customer_id: Any, idx: int) -> dict[str, Any]:
    unit_price = float(df_row.get("unit_price_usd", 0) or 0)
    qty = int(df_row.get("quantity", 1) or 1)
    try:
        delivery = datetime.fromisoformat(str(df_row.get("transaction_date", datetime.utcnow().isoformat())))
    except (ValueError, TypeError):
        delivery = datetime.utcnow() - timedelta(days=random.randint(1, 30))
    return {
        "customer_id": customer_id,
        "sku": f"KAG-SKU-{str(df_row.get('product', 'UNKNOWN'))[:16]}",
        "product_name": str(df_row.get("product", "Unknown Product"))[:128],
        "category": str(df_row.get("industry", "general"))[:32],
        "product_value": round(unit_price * qty, 2),
        "expected_weight": round(random.uniform(0.2, 5.0), 2),
        "payment_method": str(df_row.get("payment_method", "card"))[:16],
        "payment_method_risk_score": random.randint(0, 40),
        "delivery_date": delivery,
        "delivery_status": "delivered" if str(df_row.get("order_status", "delivered")).lower() != "cancelled" else "cancelled",
    }


def map_return_record(df_row: dict[str, Any], order_id: Any, customer_id: Any, idx: int) -> dict[str, Any] | None:
    return_flag = int(df_row.get("return_flag", 0) or 0)
    if return_flag != 1:
        return None
    support_count = int(df_row.get("support_tickets", 0) or 0)
    is_fraud = support_count > 3 or random.random() < 0.15
    reasons = [
        "Item arrived damaged, requesting full refund.",
        "Product not as described, need to return.",
        "Received wrong item, want replacement or refund.",
        "Package was empty upon arrival, urgent refund please.",
        "Item stopped working after one use, need immediate refund.",
    ]
    legit_reasons = [
        "Changed mind, item still in original packaging.",
        "Ordered wrong size, need to exchange.",
        "No longer needed, returning unused item.",
        "Found better price elsewhere.",
    ]
    reason = random.choice(reasons) if is_fraud else random.choice(legit_reasons)
    returned_weight = round(random.uniform(0.0, 0.3), 2) if is_fraud else round(random.uniform(0.5, 4.5), 2)
    return {
        "order_id": order_id,
        "customer_id": customer_id,
        "return_reason": reason,
        "chat_transcript": f"Customer said: {reason}",
        "email_text": f"Re: Order {str(df_row.get('order_id', ''))[:16]} — {reason}",
        "returned_weight": returned_weight,
        "condition_reported": random.choice(["empty_box", "damaged"]) if is_fraud else random.choice(["unused", "opened", "good"]),
    }


def import_dataset(session: Session, dataset_path: str, batch_size: int = 250, max_rows: int = 5000) -> dict[str, Any]:
    files = find_dataset_files(dataset_path)
    if not files:
        return {"error": f"No CSV or Parquet files found in {dataset_path}", "imported": 0}

    total_customers = 0
    total_orders = 0
    total_returns = 0
    total_cases = 0
    total_fraud_scores = 0
    skipped_no_return = 0

    for file_path in files:
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path, nrows=max_rows)
        elif file_path.endswith(".parquet"):
            df = pd.read_parquet(file_path)
            df = df.head(max_rows)

        missing = validate_schema(df)
        if missing:
            continue

        df = df.dropna(subset=REQUIRED_SOURCE_COLUMNS[:3])
        existing_order_ids = set(
            session.query(Order.sku).filter(Order.sku.like("KAG-SKU-%")).all()
        )
        existing_order_ids = {r[0] for r in existing_order_ids}

        customers_cache: dict[str, Any] = {}
        batch_orders: list[Order] = []
        batch_returns: list[ReturnRecord] = []
        batch_cases: list[ReturnCase] = []
        batch_scores: list[FraudScore] = []

        for idx, (_, row) in enumerate(df.iterrows()):
            row_dict = row.to_dict()
            order_sku = f"KAG-SKU-{str(row_dict.get('product', 'UNKNOWN'))[:16]}-{idx}"
            if order_sku in existing_order_ids:
                continue

            customer_key = str(row_dict.get("customer_id", idx))
            if customer_key not in customers_cache:
                cust_data = map_customer(row_dict, idx)
                customer = Customer(**cust_data)
                session.add(customer)
                session.flush()
                customers_cache[customer_key] = customer.id
                total_customers += 1
            else:
                customer = session.get(Customer, customers_cache[customer_key])

            order_data = map_order(row_dict, customers_cache[customer_key], idx)
            order = Order(**order_data)
            session.add(order)
            session.flush()
            batch_orders.append(order)
            total_orders += 1

            return_payload = map_return_record(row_dict, order.id, customers_cache[customer_key], idx)
            if return_payload is None:
                skipped_no_return += 1
                continue

            return_record = ReturnRecord(**return_payload)
            session.add(return_record)
            session.flush()
            batch_returns.append(return_record)
            total_returns += 1

            days_to_delivery = int(row_dict.get("days_to_delivery", 7) or 7)
            support_tickets = int(row_dict.get("support_tickets", 0) or 0)
            churn_prob = float(row_dict.get("churn_probability", 0.3) or 0.3)

            rule_score = min(100, int(
                (support_tickets > 2) * 40 + (return_record.returned_weight < 0.3) * 30 +
                (churn_prob > 0.7) * 20 + random.randint(0, 15)
            ))
            ml_score = min(100, int(rule_score * random.uniform(0.7, 1.3)))
            nlp_score = min(100, int(
                ("empty" in return_record.return_reason.lower()) * 50 +
                ("refund now" in return_record.return_reason.lower()) * 40 +
                ("urgent" in return_record.return_reason.lower()) * 30 +
                random.randint(0, 20)
            ))
            anomaly_score = min(100, int(
                (return_record.returned_weight < 0.2) * 50 +
                (days_to_delivery < 3) * 25 +
                (support_tickets > 4) * 30 +
                random.randint(0, 15)
            ))
            final_score = int(rule_score * 0.3 + ml_score * 0.3 + nlp_score * 0.2 + anomaly_score * 0.2)

            risk_level = "HIGH" if final_score >= 65 else "MEDIUM" if final_score >= 35 else "LOW"
            decision = (
                "HOLD_REFUND_HIGH_RISK" if final_score >= 70 else
                "MANUAL_REVIEW" if final_score >= 40 else
                "AUTO_APPROVE"
            )

            case = ReturnCase(
                return_id=return_record.id,
                risk_score=final_score,
                risk_level=risk_level,
                decision=decision,
                status="OPEN" if decision != "AUTO_APPROVE" else "CLOSED",
                recommended_action=(
                    "Hold refund and assign to senior fraud analyst" if final_score >= 70 else
                    "Review manually" if final_score >= 40 else
                    "Approve refund automatically"
                ),
                assigned_to=None if decision == "AUTO_APPROVE" else "analyst.kaggle",
            )
            session.add(case)
            session.flush()
            batch_cases.append(case)
            total_cases += 1

            reason_codes = []
            if return_record.returned_weight < 0.3:
                reason_codes.append("Weight mismatch detected")
            if support_tickets > 2:
                reason_codes.append(f"High support ticket count ({support_tickets})")
            if "empty" in return_record.return_reason.lower():
                reason_codes.append("Empty box claim")
            if days_to_delivery < 3:
                reason_codes.append("Fast return after delivery")

            session.add(FraudScore(
                return_id=return_record.id,
                rule_score=rule_score,
                structured_ml_score=ml_score,
                nlp_score=nlp_score,
                anomaly_score=anomaly_score,
                final_score=final_score,
                reason_codes_json=json.dumps(reason_codes or ["Kaggle imported case"]),
                explanation="Imported from Kaggle e-commerce dataset.",
            ))
            batch_scores.append(FraudScore)
            total_fraud_scores += 1

            if len(batch_orders) % batch_size == 0:
                session.commit()

        session.commit()

    return {
        "imported": True,
        "files_processed": len(files),
        "customers": total_customers,
        "orders": total_orders,
        "returns_with_flag": total_returns,
        "cases_created": total_cases,
        "fraud_scores": total_fraud_scores,
        "skipped_no_return_flag": skipped_no_return,
        "total_rows_processed": total_orders + total_returns,
    }


def import_from_kaggle_id(session: Session, dataset_id: str,
                           batch_size: int = 250, max_rows: int = 5000) -> dict[str, Any]:
    try:
        import kagglehub
        path = kagglehub.dataset_download(dataset_id)
        return import_dataset(session, path, batch_size=batch_size, max_rows=max_rows)
    except Exception as exc:
        return {"error": str(exc), "imported": 0}


def list_available_datasets() -> list[dict[str, str]]:
    return [
        {"id": "akrambelha/global-e-commerce-dataset-1m-records-20242026",
         "name": "Global E-Commerce Dataset (+1M Records, 2024-2026)",
         "size": "~506 MB", "records": "1M+", "description": "Large synthetic e-commerce transactions with return flags, customer segments, support tickets, and churn data."},
    ]


KAGGLE_DATASETS_CATALOG = list_available_datasets()
