from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlmodel import Session, select

from backend.app.models import (
    AnalystFeedback,
    Customer,
    FraudScore,
    ModelTrainingRun,
    Order,
    ReturnCase,
    ReturnRecord,
    Rule,
)


FIRST_NAMES = ["Ava", "Noah", "Mia", "Liam", "Zoe", "Ethan", "Iris", "Leo", "Nina", "Arjun"]
LAST_NAMES = ["Patel", "Garcia", "Smith", "Brown", "Khan", "Jones", "Silva", "Wang", "Davis", "Taylor"]
PRODUCTS = [
    ("SKU-1001", "Noise Cancelling Headphones", "electronics", 249.0, 0.9),
    ("SKU-1002", "Designer Jacket", "apparel", 420.0, 0.8),
    ("SKU-1003", "Smart Watch", "electronics", 299.0, 0.4),
    ("SKU-1004", "Luxury Sneakers", "apparel", 650.0, 0.7),
    ("SKU-1005", "Compact Camera", "electronics", 899.0, 1.1),
    ("SKU-1006", "Espresso Machine", "home", 799.0, 7.8),
    ("SKU-1007", "Premium Vacuum", "home", 429.0, 5.2),
    ("SKU-1008", "Gaming Console", "electronics", 499.0, 3.0),
]

FRAUD_REASONS = [
    "Box arrived empty, request full refund.",
    "Item not received even though tracking says delivered.",
    "Product is damaged and unusable, need refund now.",
    "I want a refund immediately, or I will open a chargeback.",
    "Same issue as before, please process refund fast.",
    "Package had nothing inside and the seal was broken.",
]

LEGIT_REASONS = [
    "Size did not fit, requesting a normal return.",
    "Changed mind after delivery, item unused.",
    "Purchased wrong color, would like to return it.",
    "Ordered duplicate by mistake, returning the extra item.",
]


@dataclass
class SyntheticReturn:
    customer: dict[str, Any]
    order: dict[str, Any]
    return_record: dict[str, Any]
    label: int


def _customer(idx: int, shared_address: str | None = None, shared_device: str | None = None) -> dict[str, Any]:
    name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
    address = shared_address or f"{100 + idx} Market Street, Apt {idx % 12 + 1}"
    device_id = shared_device or f"device-{idx % 37:03d}"
    return {
        "name": name,
        "email": f"{name.lower().replace(' ', '.')}@example.com",
        "phone": f"+1-202-555-{1000 + idx:04d}",
        "account_age_days": random.randint(5, 1500),
        "lifetime_orders": random.randint(1, 45),
        "lifetime_returns": random.randint(0, 12),
        "address": address,
        "device_id": device_id,
    }


def _order(customer_id: UUID, idx: int, product: tuple[str, str, str, float, float], high_risk: bool = False) -> dict[str, Any]:
    sku, product_name, category, value, weight = product
    if high_risk:
        value = value * random.uniform(1.5, 3.2)
    delivery_date = datetime.utcnow() - timedelta(hours=random.randint(2, 240))
    return {
        "customer_id": customer_id,
        "sku": sku,
        "product_name": product_name,
        "category": category,
        "product_value": round(value, 2),
        "expected_weight": round(weight, 2),
        "payment_method": random.choice(["card", "wallet", "bnpl"]),
        "payment_method_risk_score": random.randint(0, 40),
        "delivery_date": delivery_date,
        "delivery_status": "delivered",
    }


def _return(customer_id: UUID, order_id: UUID, idx: int, product_value: float, high_risk: bool = False) -> dict[str, Any]:
    if high_risk:
        reason = random.choice(FRAUD_REASONS)
        returned_weight = max(0.0, round(random.uniform(0.0, 0.4), 2))
        condition = random.choice(["empty_box", "damaged", "missing_item"])
    else:
        reason = random.choice(LEGIT_REASONS)
        returned_weight = round(random.uniform(0.6, 1.3), 2)
        condition = random.choice(["unused", "opened", "good"])
    return {
        "order_id": order_id,
        "customer_id": customer_id,
        "return_reason": reason,
        "chat_transcript": f"Customer said: {reason}",
        "email_text": f"Hello support, {reason}",
        "returned_weight": returned_weight,
        "condition_reported": condition,
    }


def generate_synthetic_training_rows(count: int = 500) -> tuple[list[dict[str, Any]], list[int], list[str]]:
    rows: list[dict[str, Any]] = []
    labels: list[int] = []
    texts: list[str] = []
    for idx in range(count):
        product = random.choice(PRODUCTS)
        high_risk = random.random() > 0.7
        customer = _customer(idx, shared_address="88 Fraud Lane" if idx % 11 == 0 else None, shared_device="device-fraud" if idx % 13 == 0 else None)
        customer_id = uuid4()
        order = _order(customer_id, idx, product, high_risk=high_risk)
        return_record = _return(customer_id, uuid4(), idx, order["product_value"], high_risk=high_risk)
        return_record["return_date"] = datetime.utcnow() - timedelta(hours=random.randint(1, 120))
        features = {
            "product_value": order["product_value"],
            "customer_account_age_days": customer["account_age_days"],
            "lifetime_orders": customer["lifetime_orders"],
            "lifetime_returns": customer["lifetime_returns"],
            "return_rate_30d": min(1.0, customer["lifetime_returns"] / max(customer["lifetime_orders"], 1)),
            "return_rate_90d": min(1.0, customer["lifetime_returns"] / max(customer["lifetime_orders"], 1)),
            "customer_return_count_30d": customer["lifetime_returns"] if high_risk else random.randint(0, 4),
            "hours_after_delivery": random.randint(2, 36) if high_risk else random.randint(24, 220),
            "expected_weight": order["expected_weight"],
            "returned_weight": return_record["returned_weight"],
            "weight_difference": abs(order["expected_weight"] - return_record["returned_weight"]),
            "payment_method_risk_score": order["payment_method_risk_score"],
            "chargeback_count": random.randint(1, 3) if high_risk and idx % 5 == 0 else 0,
            "address_reuse_count": 3 if idx % 11 == 0 else random.randint(0, 2),
            "same_device_account_count": 3 if idx % 13 == 0 else random.randint(0, 2),
            "previous_fraud_count": 1 if high_risk and idx % 7 == 0 else 0,
        }
        rows.append(features)
        labels.append(1 if high_risk or features["weight_difference"] > 0.8 or features["customer_return_count_30d"] >= 5 else 0)
        texts.append(return_record["return_reason"])
    return rows, labels, texts


def seed_database(session: Session) -> None:
    if session.exec(select(Customer)).first():
        return

    random.seed(42)

    rules = json_rules = None
    from pathlib import Path
    import json

    rules_path = Path(__file__).resolve().parents[1] / "rules" / "default_rules.json"
    json_rules = json.loads(rules_path.read_text())
    for raw_rule in json_rules:
        session.add(Rule(**raw_rule))

    shared_address = "88 Fraud Lane"
    shared_device = "device-fraud"
    customers: list[Customer] = []
    for idx in range(18):
        ring_member = idx < 5
        customer = Customer(**_customer(
            idx,
            shared_address=shared_address if ring_member or idx % 4 == 0 else None,
            shared_device=shared_device if ring_member or idx % 3 == 0 else None,
        ))
        customers.append(customer)
        session.add(customer)
    session.flush()

    orders: list[Order] = []
    returns: list[ReturnRecord] = []

    for idx in range(105):
        customer = random.choice(customers)
        ring_case = idx < 5
        product = PRODUCTS[4] if ring_case else random.choice(PRODUCTS)
        high_risk = ring_case or idx % 6 == 0 or idx in {1, 7, 12, 18, 25, 44, 67, 88}
        order = Order(**_order(customer.id, idx, product, high_risk=high_risk))
        session.add(order)
        session.flush()
        orders.append(order)
        return_payload = _return(customer.id, order.id, idx, order.product_value, high_risk=high_risk)
        if ring_case:
            order.payment_method = "card"
            order.payment_method_risk_score = 40
            order.product_value = 1299.0
            order.expected_weight = 1.1
            return_payload.update({
                "return_reason": "Product box was empty when delivered, need urgent refund.",
                "chat_transcript": "Customer repeats the same refund script used by linked accounts.",
                "email_text": "Urgent refund please. Box was empty when delivered.",
                "returned_weight": 0.05,
                "condition_reported": "empty_box",
            })
        return_record = ReturnRecord(
            **return_payload,
            return_date=datetime.utcnow() - timedelta(hours=random.randint(1, 96)),
        )
        session.add(return_record)
        session.flush()
        returns.append(return_record)

        case_score = 80 if high_risk else 28 if idx % 5 else 53
        decision = "HOLD_REFUND_HIGH_RISK" if case_score >= 70 else "MANUAL_REVIEW" if case_score >= 40 else "AUTO_APPROVE"
        risk_level = "HIGH" if case_score >= 70 else "MEDIUM" if case_score >= 40 else "LOW"
        case = ReturnCase(
            return_id=return_record.id,
            risk_score=case_score,
            risk_level=risk_level,
            decision=decision,
            status="OPEN" if decision != "AUTO_APPROVE" else "CLOSED",
            recommended_action="Hold refund and assign to senior fraud analyst" if decision == "HOLD_REFUND_HIGH_RISK" else "Review manually" if decision == "MANUAL_REVIEW" else "Approve refund automatically",
            assigned_to="analyst.jordan" if decision != "AUTO_APPROVE" else None,
        )
        session.add(case)
        session.flush()
        session.add(
            FraudScore(
                return_id=return_record.id,
                rule_score=65 if high_risk else 18,
                structured_ml_score=78 if high_risk else 22,
                nlp_score=84 if high_risk else 14,
                anomaly_score=73 if high_risk else 21,
                final_score=case_score,
                reason_codes_json=json.dumps([
                    "Weight mismatch detected" if high_risk else "Low recent return activity",
                    "Shared device/address pattern" if high_risk else "Normal customer behavior",
                ]),
                explanation="Seeded demo case",
            )
        )

        if high_risk and idx % 9 == 0:
            session.add(
                AnalystFeedback(
                    case_id=case.id,
                    analyst_decision="Mark Confirmed Fraud",
                    confirmed_label="confirmed_fraud",
                    notes="Seed confirmation for training labels",
                )
            )

    session.add(
        ModelTrainingRun(
            model_version="v0-seeded",
            precision=0.84,
            recall=0.79,
            f1=0.81,
            labels_collected=32,
            completed_at=datetime.utcnow(),
        )
    )
    session.commit()
