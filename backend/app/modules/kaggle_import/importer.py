from __future__ import annotations

import json
import os
import random
import re
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import numpy as np
import pandas as pd

from backend.app.db.session import Session
from backend.app.models import (
    Customer,
    FraudScore,
    Order,
    ReturnCase,
    ReturnRecord,
)

# ---------------------------------------------------------------------------
# Model field registry — what we can map source columns to
# ---------------------------------------------------------------------------

MODEL_FIELDS = {
    "customer": {
        "customer_id": {"type": "string", "required": True, "description": "Unique customer identifier"},
        "customer_name": {"type": "string", "required": False, "description": "Customer display name"},
        "customer_email": {"type": "string", "required": False, "description": "Email address"},
        "customer_phone": {"type": "string", "required": False, "description": "Phone number"},
        "account_age_days": {"type": "int", "required": False, "description": "Days since account creation"},
        "customer_address": {"type": "string", "required": False, "description": "Street address"},
        "country": {"type": "string", "required": False, "description": "Country code / name"},
        "lifetime_orders": {"type": "int", "required": False, "description": "Total orders ever placed"},
        "lifetime_returns": {"type": "int", "required": False, "description": "Total returns ever made"},
        "device_id": {"type": "string", "required": False, "description": "Device fingerprint"},
    },
    "order": {
        "order_id": {"type": "string", "required": True, "description": "Unique order identifier"},
        "product_name": {"type": "string", "required": True, "description": "Product / item name"},
        "product_value": {"type": "float", "required": True, "description": "Unit price or total value"},
        "category": {"type": "string", "required": False, "description": "Product category / industry"},
        "quantity": {"type": "int", "required": False, "description": "Number of units purchased"},
        "payment_method": {"type": "string", "required": False, "description": "Payment method"},
        "order_status": {"type": "string", "required": False, "description": "Order delivery status"},
        "delivery_date": {"type": "datetime", "required": False, "description": "Transaction / delivery date"},
        "shipping_cost": {"type": "float", "required": False, "description": "Shipping cost"},
    },
    "return": {
        "return_flag": {"type": "int", "required": False, "description": "1 if this row is a return, 0 otherwise"},
        "return_reason": {"type": "string", "required": True, "description": "Text reason for the return"},
        "returned_weight": {"type": "float", "required": False, "description": "Weight of returned item"},
        "condition_reported": {"type": "string", "required": False, "description": "Condition of returned item"},
        "support_tickets": {"type": "int", "required": False, "description": "Number of support tickets"},
        "days_to_delivery": {"type": "int", "required": False, "description": "Days from order to delivery"},
        "churn_probability": {"type": "float", "required": False, "description": "Customer churn probability"},
    },
    "fraud": {
        "is_fraud": {"type": "int", "required": False, "description": "1 if known fraud, 0 otherwise"},
    },
}

FLAT_MODEL_FIELDS: dict[str, dict[str, Any]] = {}
for group in MODEL_FIELDS.values():
    FLAT_MODEL_FIELDS.update(group)

# ---------------------------------------------------------------------------
# Auto-detect: common column name patterns
# ---------------------------------------------------------------------------

AUTO_MAP_PATTERNS: dict[str, list[re.Pattern]] = {
    "customer_id": [re.compile(p, re.I) for p in [
        r"^customer[_\-]?id$", r"^cust[_\-]?id$", r"^user[_\-]?id$",
        r"^buyer[_\-]?id$", r"^client[_\-]?id$", r"^member[_\-]?id$",
    ]],
    "customer_name": [re.compile(p, re.I) for p in [
        r"^customer[_\-]?name$", r"^cust[_\-]?name$", r"^user[_\-]?name$",
        r"^full[_\-]?name$", r"^name$", r"^buyer[_\-]?name$",
    ]],
    "customer_email": [re.compile(p, re.I) for p in [
        r"^email$", r"^e?mail$", r"^customer[_\-]?email$", r"^user[_\-]?email$",
    ]],
    "customer_phone": [re.compile(p, re.I) for p in [
        r"^phone$", r"^phone[_\-]?number$", r"^telephone$", r"^contact[_\-]?no$",
    ]],
    "account_age_days": [re.compile(p, re.I) for p in [
        r"^account[_\-]?age", r"^customer[_\-]?tenure", r"^tenure[_\-]?days",
        r"^days[_\-]?since[_\-]?signup", r"^member[_\-]?since",
    ]],
    "customer_address": [re.compile(p, re.I) for p in [
        r"^address$", r"^customer[_\-]?address$", r"^shipping[_\-]?address$",
        r"^location$", r"^street$",
    ]],
    "country": [re.compile(p, re.I) for p in [
        r"^country$", r"^region$", r"^nation$", r"^cntry$",
    ]],
    "lifetime_orders": [re.compile(p, re.I) for p in [
        r"^lifetime[_\-]?orders$", r"^total[_\-]?orders$", r"^orders[_\-]?count$",
        r"^frequency[_\-]?orders$", r"^order[_\-]?frequency$",
    ]],
    "lifetime_returns": [re.compile(p, re.I) for p in [
        r"^lifetime[_\-]?returns$", r"^total[_\-]?returns$", r"^returns[_\-]?count$",
        r"^return[_\-]?count$",
    ]],
    "device_id": [re.compile(p, re.I) for p in [
        r"^device[_\-]?id$", r"^device$", r"^fingerprint$",
    ]],
    "order_id": [re.compile(p, re.I) for p in [
        r"^order[_\-]?id$", r"^ord[_\-]?id$", r"^order[_\-]?number$",
        r"^transaction[_\-]?id$", r"^txn[_\-]?id$", r"^invoice[_\-]?no$",
        r"^invoice[_\-]?id$", r"^ref[_\-]?number$",
    ]],
    "product_name": [re.compile(p, re.I) for p in [
        r"^product[_\-]?name$", r"^product$", r"^item[_\-]?name$", r"^item$",
        r"^product[_\-]?title$", r"^sku[_\-]?name$", r"^description$",
    ]],
    "product_value": [re.compile(p, re.I) for p in [
        r"^price$", r"^unit[_\-]?price", r"^amount$", r"^value$",
        r"^product[_\-]?value$", r"^total$", r"^revenue", r"^sales",
        r"^unit[_\-]?price[_\-]?usd$",
    ]],
    "category": [re.compile(p, re.I) for p in [
        r"^category$", r"^industry$", r"^product[_\-]?category$",
        r"^department$", r"^segment$",
    ]],
    "quantity": [re.compile(p, re.I) for p in [
        r"^quantity$", r"^qty$", r"^count$", r"^units$", r"^num[_\-]?items$",
    ]],
    "payment_method": [re.compile(p, re.I) for p in [
        r"^payment[_\-]?method$", r"^payment$", r"^pay[_\-]?method$",
        r"^payment[_\-]?type$", r"^card[_\-]?type$",
    ]],
    "order_status": [re.compile(p, re.I) for p in [
        r"^order[_\-]?status$", r"^status$", r"^delivery[_\-]?status$",
        r"^ship[_\-]?status$",
    ]],
    "delivery_date": [re.compile(p, re.I) for p in [
        r"^delivery[_\-]?date$", r"^transaction[_\-]?date$",
        r"^order[_\-]?date$", r"^purchase[_\-]?date$", r"^date$",
        r"^order[_\-]?timestamp$", r"^created[_\-]?at$",
    ]],
    "shipping_cost": [re.compile(p, re.I) for p in [
        r"^shipping[_\-]?cost", r"^freight", r"^delivery[_\-]?charge",
        r"^postage", r"^ship[_\-]?charge",
    ]],
    "return_flag": [re.compile(p, re.I) for p in [
        r"^return[_\-]?flag$", r"^is[_\-]?return", r"^returned$",
        r"^return[_\-]?status$", r"^return$", r"^is[_\-]?refund",
    ]],
    "return_reason": [re.compile(p, re.I) for p in [
        r"^return[_\-]?reason", r"^reason$", r"^refund[_\-]?reason",
        r"^notes$", r"^customer[_\-]?notes$", r"^return[_\-]?text$",
        r"^comment",
    ]],
    "returned_weight": [re.compile(p, re.I) for p in [
        r"^returned[_\-]?weight", r"^weight", r"^item[_\-]?weight",
        r"^ship[_\-]?weight",
    ]],
    "condition_reported": [re.compile(p, re.I) for p in [
        r"^condition", r"^item[_\-]?condition", r"^product[_\-]?condition",
        r"^return[_\-]?condition",
    ]],
    "support_tickets": [re.compile(p, re.I) for p in [
        r"^support[_\-]?tickets?", r"^tickets?$", r"^support[_\-]?count",
        r"^complaints?$",
    ]],
    "days_to_delivery": [re.compile(p, re.I) for p in [
        r"^days[_\-]?to[_\-]?delivery", r"^delivery[_\-]?days",
        r"^shipping[_\-]?days", r"^lead[_\-]?time",
    ]],
    "churn_probability": [re.compile(p, re.I) for p in [
        r"^churn", r"^churn[_\-]?prob", r"^attrition",
    ]],
    "is_fraud": [re.compile(p, re.I) for p in [
        r"^is[_\-]?fraud", r"^fraud[_\-]?flag", r"^fraud$",
        r"^confirmed[_\-]?fraud", r"^label$",
    ]],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def find_dataset_files(dataset_path: str) -> list[str]:
    files = []
    for root, _dirs, fnames in os.walk(dataset_path):
        for f in fnames:
            if f.endswith(".csv") or f.endswith(".parquet"):
                files.append(os.path.join(root, f))
    return sorted(files)


def auto_detect_mapping(columns: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    used_source_cols: set[str] = set()

    for target_field, patterns in AUTO_MAP_PATTERNS.items():
        for col in columns:
            if col in used_source_cols:
                continue
            for pat in patterns:
                if pat.fullmatch(col.strip()):
                    mapping[target_field] = col
                    used_source_cols.add(col)
                    break
            if target_field in mapping:
                break
    return mapping


def preview_dataset(dataset_path: str, max_preview_rows: int = 100) -> dict[str, Any]:
    files = find_dataset_files(dataset_path)
    if not files:
        return {"error": "No CSV or Parquet files found", "columns": [], "sample_rows": []}

    df = _read_first_file(files[0], max_preview_rows)
    if df is None or df.empty:
        return {"error": "Failed to read dataset", "columns": [], "sample_rows": []}

    columns = list(df.columns)
    dtypes = {col: str(df[col].dtype) for col in columns}
    sample_rows = df.head(min(10, max_preview_rows)).fillna("").to_dict(orient="records")
    sample_rows_clean = [{k: str(v)[:200] for k, v in row.items()} for row in sample_rows]

    auto_mapping = auto_detect_mapping(columns)

    return {
        "file": os.path.basename(files[0]),
        "total_files": len(files),
        "columns": columns,
        "dtypes": dtypes,
        "sample_rows": sample_rows_clean,
        "total_rows_in_preview": len(df),
        "auto_mapping": auto_mapping,
        "model_fields": FLAT_MODEL_FIELDS,
    }


def _read_first_file(file_path: str, nrows: int) -> pd.DataFrame | None:
    try:
        if file_path.endswith(".parquet"):
            df = pd.read_parquet(file_path)
            return df.head(nrows) if len(df) > nrows else df
        return pd.read_csv(file_path, nrows=nrows, encoding="utf-8", low_memory=False)
    except UnicodeDecodeError:
        try:
            return pd.read_csv(file_path, nrows=nrows, encoding="latin-1", low_memory=False)
        except Exception:
            return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Dynamic import with user-provided mapping
# ---------------------------------------------------------------------------

SUPPORTED_TYPES = {"string", "int", "float", "datetime"}


def _cast(value: Any, target_type: str) -> Any:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if target_type == "int":
        return int(float(str(value)))
    if target_type == "float":
        return float(str(value))
    if target_type == "datetime":
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return datetime.utcnow()
    return str(value)[:512]


def import_with_mapping(
    session: Session,
    dataset_path: str,
    mapping: dict[str, str],
    batch_size: int = 250,
    max_rows: int = 5000,
    default_return_reason: str = "Return requested by customer.",
) -> dict[str, Any]:
    files = find_dataset_files(dataset_path)
    if not files:
        return {"error": "No CSV or Parquet files found", "imported": False}

    total_customers = 0
    total_orders = 0
    total_returns = 0
    total_cases = 0
    total_fraud_scores = 0
    skipped_no_return = 0

    src_cid = mapping.get("customer_id")
    src_name = mapping.get("customer_name")
    src_email = mapping.get("customer_email")
    src_phone = mapping.get("customer_phone")
    src_age = mapping.get("account_age_days")
    src_addr = mapping.get("customer_address")
    src_country = mapping.get("country")
    src_lt_orders = mapping.get("lifetime_orders")
    src_lt_returns = mapping.get("lifetime_returns")
    src_device = mapping.get("device_id")

    src_oid = mapping.get("order_id")
    src_product = mapping.get("product_name")
    src_price = mapping.get("product_value")
    src_cat = mapping.get("category")
    src_qty = mapping.get("quantity")
    src_payment = mapping.get("payment_method")
    src_status = mapping.get("order_status")
    src_delivery = mapping.get("delivery_date")
    src_shipping = mapping.get("shipping_cost")

    src_return_flag = mapping.get("return_flag")
    src_return_reason = mapping.get("return_reason")
    src_returned_weight = mapping.get("returned_weight")
    src_condition = mapping.get("condition_reported")
    src_tickets = mapping.get("support_tickets")
    src_delivery_days = mapping.get("days_to_delivery")
    src_churn = mapping.get("churn_probability")
    src_fraud = mapping.get("is_fraud")

    for file_path in files:
        df = _read_first_file(file_path, max_rows)
        if df is None or df.empty:
            continue

        df = df.dropna(how="all").reset_index(drop=True)
        if src_cid:
            df = df.dropna(subset=[src_cid])

        existing_skus: set[str] = set()
        try:
            rows = session.query(Order.sku).filter(Order.sku.like("KAG-SKU-%")).all()
            existing_skus = {r[0] for r in rows}
        except Exception:
            pass

        customers_cache: dict[str, UUID] = {}
        row_idx = 0

        for _, row in df.iterrows():
            row_dict = row.to_dict()
            row_idx += 1

            customer_key = str(_cast(row_dict.get(src_cid), "string") if src_cid else f"auto-{row_idx}")

            if customer_key not in customers_cache:
                name = src_name or str(_cast(row_dict.get(src_cid), "string") if src_cid else f"User-{row_idx}")
                cid = str(_cast(row_dict.get(src_cid), "string")) if src_cid else f"kaggle-{row_idx}"
                cust = Customer(
                    name=str(_cast(row_dict.get(src_name) if src_name else cid, "string"))[:128] if src_name else f"K-User-{cid[:16]}",
                    email=str(_cast(row_dict.get(src_email), "string") if src_email else f"user.{cid[:12]}@kaggle.local")[:128],
                    phone=str(_cast(row_dict.get(src_phone), "string") if src_phone else f"+1-555-{(row_idx % 9000) + 1000:04d}")[:32],
                    account_age_days=int(_cast(row_dict.get(src_age), "int") if src_age else random.randint(1, 1500) or 1),
                    lifetime_orders=int(_cast(row_dict.get(src_lt_orders), "int") if src_lt_orders else random.randint(1, 30) or 1),
                    lifetime_returns=int(_cast(row_dict.get(src_lt_returns), "int") if src_lt_returns else random.randint(0, 8) or 0),
                    address=str(_cast(row_dict.get(src_addr), "string") if src_addr else f"{100 + row_idx} Import St, {_cast(row_dict.get(src_country), 'string') or 'Unknown'}")[:256],
                    device_id=str(_cast(row_dict.get(src_device), "string") if src_device else f"kaggle-dev-{row_idx % 500:03d}")[:64],
                )
                session.add(cust)
                session.flush()
                customers_cache[customer_key] = cust.id
                total_customers += 1
            else:
                cust = session.get(Customer, customers_cache[customer_key])

            order_key = str(_cast(row_dict.get(src_oid), "string") if src_oid else f"ORD-{row_idx}")
            sku = f"KAG-SKU-{order_key[:32]}"
            if sku in existing_skus:
                skipped_no_return += 1
                continue

            product_name = str(_cast(row_dict.get(src_product), "string") if src_product else "Unknown Product")[:128]
            raw_price = _cast(row_dict.get(src_price), "float") if src_price else random.uniform(20, 500)
            qty = int(_cast(row_dict.get(src_qty), "int") if src_qty else 1 or 1)
            delivery_dt = _cast(row_dict.get(src_delivery), "datetime") if src_delivery else datetime.utcnow() - timedelta(days=random.randint(1, 30))

            order = Order(
                customer_id=customers_cache[customer_key],
                sku=sku,
                product_name=product_name,
                category=str(_cast(row_dict.get(src_cat), "string") if src_cat else "general")[:32],
                product_value=round(float(raw_price) * qty, 2),
                expected_weight=round(random.uniform(0.2, 5.0), 2),
                payment_method=str(_cast(row_dict.get(src_payment), "string") if src_payment else "card")[:16],
                payment_method_risk_score=random.randint(0, 40),
                delivery_date=delivery_dt,
                delivery_status=str(_cast(row_dict.get(src_status), "string") if src_status else "delivered")[:16],
            )
            session.add(order)
            session.flush()
            total_orders += 1

            raw_return_flag = _cast(row_dict.get(src_return_flag), "int") if src_return_flag else 0
            return_flag = int(raw_return_flag) if raw_return_flag is not None else 0
            if return_flag != 1:
                skipped_no_return += 1
                continue

            ret_reason = str(_cast(row_dict.get(src_return_reason), "string") if src_return_reason else default_return_reason)[:512]
            ret_weight = _cast(row_dict.get(src_returned_weight), "float") if src_returned_weight else round(random.uniform(0.1, 4.0), 2)

            return_record = ReturnRecord(
                order_id=order.id,
                customer_id=customers_cache[customer_key],
                return_reason=ret_reason,
                chat_transcript=f"Customer said: {ret_reason}",
                email_text=f"Return request: {ret_reason}",
                returned_weight=round(float(ret_weight), 2) if ret_weight is not None else round(random.uniform(0.1, 4.0), 2),
                condition_reported=str(_cast(row_dict.get(src_condition), "string") if src_condition else random.choice(["unused", "opened", "damaged"]))[:32],
            )
            session.add(return_record)
            session.flush()
            total_returns += 1

            tickets = int(_cast(row_dict.get(src_tickets), "int") or 0) if src_tickets else random.randint(0, 5)
            days_del = int(_cast(row_dict.get(src_delivery_days), "int") or 7) if src_delivery_days else 7
            churn = float(_cast(row_dict.get(src_churn), "float") or 0.3) if src_churn else 0.3
            is_fraud_label = int(_cast(row_dict.get(src_fraud), "int") or 0) if src_fraud else 0

            empty_box = "empty" in ret_reason.lower() or "nothing inside" in ret_reason.lower()
            urgent = "urgent" in ret_reason.lower() or "immediately" in ret_reason.lower() or "refund now" in ret_reason.lower()
            weight_mismatch = return_record.returned_weight is not None and return_record.returned_weight < 0.3

            rule_score = min(100, int(
                (tickets > 2) * 30 + weight_mismatch * 30 +
                empty_box * 20 + urgent * 20 + is_fraud_label * 40 +
                random.randint(0, 10)
            ))
            ml_score = min(100, int(rule_score * random.uniform(0.7, 1.3)))
            nlp_score = min(100, int(
                empty_box * 50 + urgent * 40 +
                (tickets > 3) * 25 + random.randint(0, 15)
            ))
            anomaly_score = min(100, int(
                weight_mismatch * 40 + (days_del < 3) * 20 +
                (tickets > 4) * 25 + random.randint(0, 10)
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
            total_cases += 1

            reason_codes = []
            if weight_mismatch:
                reason_codes.append("Weight mismatch detected")
            if tickets > 2:
                reason_codes.append(f"High support ticket count ({tickets})")
            if empty_box:
                reason_codes.append("Empty box claim")
            if days_del < 3:
                reason_codes.append("Fast return after delivery")
            if urgent:
                reason_codes.append("Urgent refund language detected")

            session.add(FraudScore(
                return_id=return_record.id,
                rule_score=rule_score,
                structured_ml_score=ml_score,
                nlp_score=nlp_score,
                anomaly_score=anomaly_score,
                final_score=final_score,
                reason_codes_json=json.dumps(reason_codes or ["Imported from Kaggle dataset"]),
                explanation="Imported from Kaggle dataset with user-defined column mapping.",
            ))
            total_fraud_scores += 1

            if total_orders % batch_size == 0:
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
    }


# ---------------------------------------------------------------------------
# Top-level API: download + preview / download + import
# ---------------------------------------------------------------------------


def download_and_preview(dataset_id: str, max_preview_rows: int = 100) -> dict[str, Any]:
    try:
        import kagglehub
        path = kagglehub.dataset_download(dataset_id)
        result = preview_dataset(path, max_preview_rows=max_preview_rows)
        result["dataset_path"] = path
        result["dataset_id"] = dataset_id
        return result
    except Exception as exc:
        return {"error": str(exc), "columns": [], "sample_rows": []}


def download_and_import(
    session: Session,
    dataset_id: str,
    mapping: dict[str, str],
    batch_size: int = 250,
    max_rows: int = 5000,
) -> dict[str, Any]:
    try:
        import kagglehub
        path = kagglehub.dataset_download(dataset_id)
        return import_with_mapping(session, path, mapping, batch_size=batch_size, max_rows=max_rows)
    except Exception as exc:
        return {"error": str(exc), "imported": False}
