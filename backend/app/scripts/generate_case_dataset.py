#!/usr/bin/env python3
"""
Generate fraud case and investigation data from existing return/order/payment rows.

This script top-ups both the legacy SQLModel tables used by the original dashboard
and the production fraud-case tables used by the v1 API.

Default targets:
  - 10,000 legacy cases
  - 1,000 legacy investigations
  - 10,000 production cases
  - 1,000 production investigations

Usage:
  python -m backend.app.scripts.generate_case_dataset
  python -m backend.app.scripts.generate_case_dataset --cases 15000 --investigations 2000
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from typing import Any

from sqlalchemy import func, select
from sqlmodel import Session

from backend.app.db.session import engine
from backend.app.models import (
    AnalystFeedback as LegacyAnalystFeedback,
    Customer as LegacyCustomer,
    FraudScore as LegacyFraudScore,
    Order as LegacyOrder,
    ReturnCase as LegacyReturnCase,
    ReturnRecord as LegacyReturnRecord,
)
from backend.app.prod_models import (
    AnalystFeedback as ProdAnalystFeedback,
    Customer as ProdCustomer,
    FraudCase as ProdFraudCase,
    FraudScore as ProdFraudScore,
    Order as ProdOrder,
    Payment as ProdPayment,
    ReturnRequest as ProdReturnRequest,
    Shipment as ProdShipment,
)


logger = logging.getLogger("returnshield.scripts.generate_case_dataset")


@dataclass
class SourceRow:
    return_request: ProdReturnRequest
    customer: ProdCustomer
    order: ProdOrder
    shipment: ProdShipment | None
    payment: ProdPayment | None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> int:
    return int(max(low, min(high, round(value))))


def _text_has(text: str, needles: list[str]) -> bool:
    lowered = text.lower()
    return any(needle in lowered for needle in needles)


def _build_risk_profile(src: SourceRow, seed: int) -> dict[str, Any]:
    reason = src.return_request.return_reason or ""
    condition = src.return_request.condition_reported or ""
    payment_method = src.order.payment_method or ""
    product_name = src.order.product_name or ""
    category = src.order.category or ""
    text = " ".join([reason, condition, payment_method, product_name, category])

    expected_weight = float(src.shipment.expected_weight or 0) if src.shipment else 0.0
    returned_weight = float(src.shipment.returned_weight or 0) if src.shipment else 0.0
    weight_difference = abs(expected_weight - returned_weight)
    hours_after_delivery = float(src.return_request.hours_after_delivery or 0)
    product_value = float(src.order.product_value or 0)
    payment_risk = int(src.order.payment_method_risk_score or 0)
    chargeback = bool(src.payment.chargeback_flag) if src.payment else False
    account_age = int(src.customer.account_age_days or 0)
    lifetime_returns = int(src.customer.lifetime_returns or 0)
    lifetime_orders = int(src.customer.lifetime_orders or 0)
    repeat_rate = lifetime_returns / max(lifetime_orders, 1)

    keyword_hits = {
        "empty_box": _text_has(text, ["empty box", "nothing inside", "box was empty"]),
        "item_not_received": _text_has(text, ["never received", "not received", "not delivered"]),
        "chargeback": _text_has(text, ["chargeback", "dispute", "bank"]),
        "refund_pressure": _text_has(text, ["refund now", "urgent refund", "refund immediately"]),
        "damaged_claim": _text_has(text, ["damaged", "broken", "defective"]),
        "return_abuse": _text_has(text, ["changed mind", "duplicate", "bought for event"]),
    }

    rule_score = (
        min(weight_difference * 70, 28)
        + (18 if hours_after_delivery < 48 else 0)
        + (20 if chargeback else 0)
        + (14 if keyword_hits["empty_box"] or keyword_hits["item_not_received"] else 0)
        + (10 if repeat_rate >= 0.3 else 0)
        + (8 if product_value >= 300 else 0)
    )
    structured_score = (
        payment_risk * 1.1
        + min(product_value / 18.0, 22)
        + min(weight_difference * 35, 18)
        + (10 if account_age < 120 else 0)
        + (8 if repeat_rate >= 0.25 else 0)
    )
    nlp_score = (
        18
        + (22 if keyword_hits["refund_pressure"] else 0)
        + (20 if keyword_hits["chargeback"] else 0)
        + (18 if keyword_hits["empty_box"] else 0)
        + (18 if keyword_hits["item_not_received"] else 0)
        + (12 if keyword_hits["damaged_claim"] else 0)
        + (8 if keyword_hits["return_abuse"] else 0)
    )
    graph_score = (
        min(lifetime_returns * 6, 30)
        + (18 if account_age < 90 else 0)
        + (12 if repeat_rate >= 0.4 else 0)
        + (10 if payment_method in {"card", "upi"} else 0)
    )
    anomaly_score = (
        min(weight_difference * 60, 30)
        + (18 if chargeback else 0)
        + (12 if hours_after_delivery < 24 else 0)
        + (12 if product_value >= 500 else 0)
        + (8 if keyword_hits["refund_pressure"] else 0)
    )

    final_score = (
        rule_score * 0.35
        + structured_score * 0.25
        + nlp_score * 0.20
        + graph_score * 0.10
        + anomaly_score * 0.10
    )
    final_score = _clamp(final_score)

    reason_codes = []
    if weight_difference >= 0.25:
        reason_codes.append("WEIGHT_MISMATCH")
    if hours_after_delivery < 48:
        reason_codes.append("QUICK_RETURN")
    if chargeback:
        reason_codes.append("CHARGEBACK_FLAG")
    if keyword_hits["empty_box"]:
        reason_codes.append("EMPTY_BOX_CLAIM")
    if keyword_hits["item_not_received"]:
        reason_codes.append("ITEM_NOT_RECEIVED")
    if keyword_hits["refund_pressure"]:
        reason_codes.append("REFUND_PRESSURE")
    if keyword_hits["damaged_claim"]:
        reason_codes.append("DAMAGED_CLAIM")
    if repeat_rate >= 0.25:
        reason_codes.append("REPEAT_RETURNER")
    if account_age < 120:
        reason_codes.append("YOUNG_ACCOUNT")
    if product_value >= 500:
        reason_codes.append("HIGH_VALUE_ITEM")

    if final_score >= 70:
        decision = "HOLD_REFUND_HIGH_RISK"
        risk_level = "HIGH"
        status = "OPEN"
        priority = "P1"
        assigned_to = "analyst.senior"
        recommended_action = "Hold refund and escalate to senior fraud analyst"
    elif final_score >= 40:
        decision = "MANUAL_REVIEW"
        risk_level = "MEDIUM"
        status = "OPEN"
        priority = "P2"
        assigned_to = "analyst.review"
        recommended_action = "Request additional verification before releasing refund"
    else:
        decision = "AUTO_APPROVE"
        risk_level = "LOW"
        status = "CLOSED"
        priority = "P3"
        assigned_to = None
        recommended_action = "Approve return automatically"

    explanation = (
        f"Seeded case from source return {seed}. "
        f"Final score {final_score}; signals: {', '.join(reason_codes[:4]) or 'none'}."
    )

    return {
        "rule_score": _clamp(rule_score),
        "structured_score": _clamp(structured_score),
        "nlp_score": _clamp(nlp_score),
        "graph_score": _clamp(graph_score),
        "anomaly_score": _clamp(anomaly_score),
        "final_score": final_score,
        "reason_codes": reason_codes,
        "decision": decision,
        "risk_level": risk_level,
        "status": status,
        "priority": priority,
        "assigned_to": assigned_to,
        "recommended_action": recommended_action,
        "explanation": explanation,
        "weight_difference": weight_difference,
        "hours_after_delivery": hours_after_delivery,
        "text": text,
        "product_value": product_value,
        "payment_method": payment_method,
        "payment_risk": payment_risk,
        "repeat_rate": repeat_rate,
    }


def _legacy_customer(src: SourceRow, idx: int) -> LegacyCustomer:
    ext = src.customer.external_customer_id or f"source-{idx}"
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in ext).strip("-") or f"cust-{idx}"
    return LegacyCustomer(
        id=uuid4(),
        name=src.customer.name or f"Customer {idx}",
        email=f"{safe}@example.com",
        phone=f"+1-202-555-{(1000 + idx) % 10000:04d}",
        account_age_days=int(src.customer.account_age_days or 0),
        lifetime_orders=int(src.customer.lifetime_orders or 0),
        lifetime_returns=int(src.customer.lifetime_returns or 0),
        address=f"{safe}-address",
        device_id=f"{safe}-device",
    )


def _legacy_order(customer_id, src: SourceRow, idx: int, profile: dict[str, Any]) -> LegacyOrder:
    delivery_date = src.order.delivery_date
    if delivery_date is None:
        delivery_date = _utc_now()
    delivery_date = delivery_date.replace(tzinfo=None) if hasattr(delivery_date, "tzinfo") else delivery_date
    expected_weight = float(src.shipment.expected_weight or 0) if src.shipment else max(float(src.order.product_value or 0) / 100.0, 0.1)
    return LegacyOrder(
        id=uuid4(),
        customer_id=customer_id,
        sku=src.order.sku or f"SKU-{idx:05d}",
        product_name=src.order.product_name or "Seed Product",
        category=src.order.category or "general",
        product_value=float(src.order.product_value or 0),
        expected_weight=expected_weight,
        payment_method=src.order.payment_method or "card",
        payment_method_risk_score=int(src.order.payment_method_risk_score or 0),
        delivery_date=delivery_date,
        delivery_status=getattr(src.order, "order_status", None) or "delivered",
    )


def _legacy_return(customer_id, order_id, src: SourceRow, idx: int, profile: dict[str, Any]) -> LegacyReturnRecord:
    return_date = src.return_request.return_date or _utc_now()
    if hasattr(return_date, "tzinfo") and return_date.tzinfo is not None:
        return_date = return_date.replace(tzinfo=None)
    chat_transcript = f"Customer message: {src.return_request.return_reason or 'Return request'}"
    email_text = f"Support email: {src.return_request.return_reason or 'Return request'}"
    returned_weight = float(src.shipment.returned_weight or 0) if src.shipment else max(float(profile["product_value"]) / 1000.0, 0.05)
    condition = src.return_request.condition_reported or "unknown"
    return LegacyReturnRecord(
        id=uuid4(),
        order_id=order_id,
        customer_id=customer_id,
        return_reason=src.return_request.return_reason or "No reason provided",
        chat_transcript=chat_transcript,
        email_text=email_text,
        returned_weight=returned_weight,
        condition_reported=condition,
        return_date=return_date,
    )


def _legacy_case(case_id, return_id, profile: dict[str, Any], idx: int) -> LegacyReturnCase:
    return LegacyReturnCase(
        id=case_id,
        return_id=return_id,
        risk_score=profile["final_score"],
        risk_level=profile["risk_level"],
        decision=profile["decision"],
        status=profile["status"],
        recommended_action=profile["recommended_action"],
        assigned_to=profile["assigned_to"],
    )


def _legacy_score(return_id, profile: dict[str, Any]) -> LegacyFraudScore:
    return LegacyFraudScore(
        id=uuid4(),
        return_id=return_id,
        rule_score=profile["rule_score"],
        structured_ml_score=profile["structured_score"],
        nlp_score=profile["nlp_score"],
        anomaly_score=profile["anomaly_score"],
        final_score=profile["final_score"],
        reason_codes_json=json.dumps(profile["reason_codes"]),
        explanation=profile["explanation"],
    )


def _prod_score(merchant_id, customer_id, return_id, profile: dict[str, Any]) -> ProdFraudScore:
    return ProdFraudScore(
        id=uuid4(),
        merchant_id=merchant_id,
        return_id=return_id,
        customer_id=customer_id,
        rule_score=profile["rule_score"],
        structured_ml_score=profile["structured_score"],
        nlp_score=profile["nlp_score"],
        graph_score=profile["graph_score"],
        anomaly_score=profile["anomaly_score"],
        final_score=profile["final_score"],
        risk_level=profile["risk_level"],
        decision=profile["decision"],
        reason_codes_json=profile["reason_codes"],
        score_breakdown_json={
            "rule_score": profile["rule_score"],
            "structured_ml_score": profile["structured_score"],
            "nlp_score": profile["nlp_score"],
            "graph_score": profile["graph_score"],
            "anomaly_score": profile["anomaly_score"],
        },
    )


def _prod_case(case_id, merchant_id, customer_id, return_id, fraud_score_id, profile: dict[str, Any], idx: int) -> ProdFraudCase:
    return ProdFraudCase(
        id=case_id,
        merchant_id=merchant_id,
        return_id=return_id,
        customer_id=customer_id,
        fraud_score_id=fraud_score_id,
        case_status=profile["status"],
        priority=profile["priority"],
        assigned_to=profile["assigned_to"],
        recommended_action=profile["recommended_action"],
        case_summary=profile["explanation"],
        closed_at=_utc_now() if profile["status"] == "CLOSED" else None,
    )


def _legacy_feedback(feedback_id, case_id, return_id, profile: dict[str, Any], idx: int) -> LegacyAnalystFeedback:
    confirmed = profile["final_score"] >= 70 or (idx % 3 == 0 and profile["final_score"] >= 40)
    return LegacyAnalystFeedback(
        id=feedback_id,
        case_id=case_id,
        analyst_decision="Mark Confirmed Fraud" if confirmed else "Mark Legitimate",
        confirmed_label="confirmed_fraud" if confirmed else "confirmed_legit",
        notes=profile["explanation"],
    )


def _prod_feedback(feedback_id, merchant_id, case_id, return_id, profile: dict[str, Any], idx: int) -> ProdAnalystFeedback:
    confirmed = profile["final_score"] >= 70 or (idx % 3 == 0 and profile["final_score"] >= 40)
    return ProdAnalystFeedback(
        id=feedback_id,
        merchant_id=merchant_id,
        case_id=case_id,
        return_id=return_id,
        analyst_decision="Mark Confirmed Fraud" if confirmed else "Mark Legitimate",
        confirmed_label="confirmed_fraud" if confirmed else "confirmed_legit",
        notes=profile["explanation"],
    )


def _legacy_count(session: Session, model) -> int:
    return int(session.exec(select(func.count(model.id))).one()[0] or 0)


def _prod_count(session: Session, model) -> int:
    return int(session.exec(select(func.count(model.id))).one()[0] or 0)


def _load_source_rows(session: Session, limit: int) -> list[SourceRow]:
    stmt = (
        select(ProdReturnRequest, ProdCustomer, ProdOrder, ProdShipment, ProdPayment)
        .join(ProdCustomer, ProdReturnRequest.customer_id == ProdCustomer.id)
        .join(ProdOrder, ProdReturnRequest.order_id == ProdOrder.id)
        .join(ProdShipment, ProdShipment.order_id == ProdOrder.id, isouter=True)
        .join(ProdPayment, ProdPayment.order_id == ProdOrder.id, isouter=True)
        .order_by(ProdReturnRequest.created_at.desc())
        .limit(limit)
    )
    rows = session.exec(stmt).all()
    return [
        SourceRow(
            return_request=ret,
            customer=customer,
            order=order,
            shipment=shipment,
            payment=payment,
        )
        for ret, customer, order, shipment, payment in rows
    ]


def run_backfill(
    session: Session,
    *,
    cases_target: int = 10_000,
    investigations_target: int = 1_000,
    batch_size: int = 250,
    seed: int = 42,
) -> dict[str, int]:
    random.seed(seed)

    legacy_case_count = _legacy_count(session, LegacyReturnCase)
    legacy_feedback_count = _legacy_count(session, LegacyAnalystFeedback)
    prod_case_count = _prod_count(session, ProdFraudCase)
    prod_feedback_count = _prod_count(session, ProdAnalystFeedback)

    legacy_needed_cases = max(0, cases_target - legacy_case_count)
    legacy_needed_feedback = max(0, investigations_target - legacy_feedback_count)
    prod_needed_cases = max(0, cases_target - prod_case_count)
    prod_needed_feedback = max(0, investigations_target - prod_feedback_count)

    if not any([legacy_needed_cases, legacy_needed_feedback, prod_needed_cases, prod_needed_feedback]):
        logger.info("Targets already met. Nothing to do.")
        return {
            "legacy_cases_added": 0,
            "legacy_feedback_added": 0,
            "prod_cases_added": 0,
            "prod_feedback_added": 0,
            "legacy_case_count": legacy_case_count,
            "legacy_feedback_count": legacy_feedback_count,
            "prod_case_count": prod_case_count,
            "prod_feedback_count": prod_feedback_count,
        }

    source_limit = max(legacy_needed_cases, legacy_needed_feedback, prod_needed_cases, prod_needed_feedback)
    source_rows = _load_source_rows(session, source_limit)
    if len(source_rows) < source_limit:
        logger.warning("Only %d source rows available, fewer than requested %d.", len(source_rows), source_limit)

    logger.info(
        "Existing counts -> legacy cases: %s, legacy feedback: %s, prod cases: %s, prod feedback: %s",
        legacy_case_count,
        legacy_feedback_count,
        prod_case_count,
        prod_feedback_count,
    )
    logger.info(
        "Top-up needed -> legacy cases: %s, legacy feedback: %s, prod cases: %s, prod feedback: %s",
        legacy_needed_cases,
        legacy_needed_feedback,
        prod_needed_cases,
        prod_needed_feedback,
    )

    primary_pending: list[Any] = []
    secondary_pending: list[Any] = []
    feedback_pending: list[Any] = []
    legacy_created = 0
    legacy_feedback_created = 0
    prod_created = 0
    prod_feedback_created = 0
    total_rows = 0

    def flush_primary() -> None:
        nonlocal primary_pending
        if not primary_pending:
            return
        session.add_all(primary_pending)
        session.commit()
        primary_pending = []

    def flush_secondary() -> None:
        nonlocal secondary_pending
        if not secondary_pending:
            return
        session.add_all(secondary_pending)
        session.commit()
        secondary_pending = []

    def flush_feedback() -> None:
        nonlocal feedback_pending
        if not feedback_pending:
            return
        session.add_all(feedback_pending)
        session.commit()
        feedback_pending = []

    for idx, src in enumerate(source_rows):
        profile = _build_risk_profile(src, idx + 1)

        if legacy_created < legacy_needed_cases:
            legacy_customer = _legacy_customer(src, idx + 1)
            legacy_order = _legacy_order(legacy_customer.id, src, idx + 1, profile)
            legacy_return = _legacy_return(legacy_customer.id, legacy_order.id, src, idx + 1, profile)
            legacy_score = _legacy_score(legacy_return.id, profile)
            legacy_case_id = uuid4()
            legacy_feedback_id = uuid4()
            legacy_case = _legacy_case(legacy_case_id, legacy_return.id, profile, idx + 1)

            primary_pending.extend([legacy_customer, legacy_order, legacy_return])
            secondary_pending.extend([legacy_score, legacy_case])
            legacy_created += 1

            if legacy_feedback_created < legacy_needed_feedback and (
                legacy_created <= legacy_needed_feedback or profile["final_score"] >= 40
            ):
                feedback_pending.append(_legacy_feedback(legacy_feedback_id, legacy_case_id, legacy_return.id, profile, idx + 1))
                legacy_feedback_created += 1

        if prod_created < prod_needed_cases:
            prod_case_id = uuid4()
            prod_feedback_id = uuid4()
            prod_score = _prod_score(src.customer.merchant_id, src.customer.id, src.return_request.id, profile)
            prod_case = _prod_case(prod_case_id, src.customer.merchant_id, src.customer.id, src.return_request.id, prod_score.id, profile, idx + 1)
            secondary_pending.extend([prod_score, prod_case])
            prod_created += 1

            if prod_feedback_created < prod_needed_feedback and (
                prod_created <= prod_needed_feedback or profile["final_score"] >= 40
            ):
                feedback_pending.append(_prod_feedback(prod_feedback_id, src.customer.merchant_id, prod_case_id, src.return_request.id, profile, idx + 1))
                prod_feedback_created += 1

        total_rows += 1
        if total_rows % batch_size == 0:
            logger.info(
                "Processed %s source rows | legacy cases=%s feedback=%s | prod cases=%s feedback=%s",
                total_rows,
                legacy_created,
                legacy_feedback_created,
                prod_created,
                prod_feedback_created,
            )
            flush_primary()
            flush_secondary()
            flush_feedback()

        if legacy_created >= legacy_needed_cases and legacy_feedback_created >= legacy_needed_feedback and prod_created >= prod_needed_cases and prod_feedback_created >= prod_needed_feedback:
            break

    flush_primary()
    flush_secondary()
    flush_feedback()

    logger.info("=" * 72)
    logger.info("Done.")
    logger.info("Legacy cases added: %s", legacy_created)
    logger.info("Legacy feedback added: %s", legacy_feedback_created)
    logger.info("Production cases added: %s", prod_created)
    logger.info("Production feedback added: %s", prod_feedback_created)
    logger.info("=" * 72)

    return {
        "legacy_cases_added": legacy_created,
        "legacy_feedback_added": legacy_feedback_created,
        "prod_cases_added": prod_created,
        "prod_feedback_added": prod_feedback_created,
        "legacy_case_count": legacy_case_count + legacy_created,
        "legacy_feedback_count": legacy_feedback_count + legacy_feedback_created,
        "prod_case_count": prod_case_count + prod_created,
        "prod_feedback_count": prod_feedback_count + prod_feedback_created,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate fraud case and investigation data from existing order/return/payment rows.")
    parser.add_argument("--cases", type=int, default=10_000, help="Target total cases per stack (legacy and production).")
    parser.add_argument("--investigations", type=int, default=1_000, help="Target total investigations/feedback rows per stack.")
    parser.add_argument("--batch-size", type=int, default=250, help="Commit every N source rows.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic field shaping.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")

    with Session(engine) as session:
        run_backfill(
            session,
            cases_target=args.cases,
            investigations_target=args.investigations,
            batch_size=args.batch_size,
            seed=args.seed,
        )


if __name__ == "__main__":
    main()
