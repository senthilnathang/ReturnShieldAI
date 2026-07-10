#!/usr/bin/env python3
"""Seed cricket-ball return demo data across legacy and production tables.

This creates 100 cricket-ball orders with matching returns and case records so
both the new return workflow and the legacy case queue have realistic data to
exercise OCR upload and fraud-case review flows.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sqlmodel import Session, select
from sqlalchemy import func, select as sa_select

from backend.app.core.database import async_session_factory, sync_engine
from backend.app.core.logging import setup_logging
from backend.app.db.base import Base as ProdBase
from backend.app.db.session import engine as legacy_engine
from backend.app.models import Customer as LegacyCustomer
from backend.app.models import FraudScore as LegacyFraudScore
from backend.app.models import Order as LegacyOrder
from backend.app.models import ReturnCase as LegacyReturnCase
from backend.app.models import ReturnRecord as LegacyReturnRecord
from backend.app.prod_models import (
    Customer as ProdCustomer,
    FraudCase as ProdFraudCase,
    FraudScore as ProdFraudScore,
    Merchant as ProdMerchant,
    Order as ProdOrder,
    Payment as ProdPayment,
    ReturnRequest as ProdReturnRequest,
    ReturnItem as ProdReturnItem,
    Shipment as ProdShipment,
    SupportInteraction as ProdSupportInteraction,
)

logger = logging.getLogger("returnshield.scripts.seed_cricket_returns")
TOTAL_ROWS = 100
LEGACY_PREFIX = "CRICKET-LEG-"
PROD_PREFIX = "CRICKET-PROD-"

PRODUCTS = [
    ("Cricket Ball - Red Leather", "RED-LEATHER", 24.99, 0.156),
    ("Cricket Ball - White Leather", "WHITE-LEATHER", 26.49, 0.154),
    ("Cricket Ball - Practice Ball", "PRACTICE", 18.99, 0.148),
    ("Cricket Ball - Test Match", "TEST-MATCH", 29.99, 0.158),
    ("Cricket Ball - Limited Edition", "LIMITED", 34.99, 0.161),
]

REASONS = [
    ("Damaged Product", "Damaged", "The seam is split and the ball is not usable.", "HOLD_REFUND_HIGH_RISK", 82),
    ("Wrong Product", "Wrong Item Received", "The package contains a different item than the cricket ball ordered.", "MANUAL_REVIEW", 66),
    ("Defective Product", "Defective", "The cricket ball is misshapen and does not bounce correctly.", "HOLD_REFUND_HIGH_RISK", 78),
    ("Empty Box", "Unknown", "The delivery looked tampered and the cricket ball was missing.", "HOLD_REFUND_HIGH_RISK", 91),
    ("Missing Accessories", "Missing Parts", "The cricket ball sleeve and accessory card were missing.", "MANUAL_REVIEW", 61),
]


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _legacy_case_score(idx: int) -> tuple[int, str, str, str]:
    base = 48 + (idx % 41)
    if idx % 5 == 0:
        return min(95, base + 18), "HIGH", "HOLD_REFUND_HIGH_RISK", "OPEN"
    if idx % 3 == 0:
        return min(84, base + 6), "MEDIUM", "MANUAL_REVIEW", "OPEN"
    return max(22, base - 12), "LOW", "AUTO_APPROVE", "OPEN"


def ensure_schema() -> None:
    ProdBase.metadata.create_all(sync_engine)
    from backend.app.models import __all__ as _legacy_models  # noqa: F401
    _ = _legacy_models
    from sqlmodel import SQLModel
    SQLModel.metadata.create_all(legacy_engine)


def _legacy_seed_rows() -> int:
    with Session(legacy_engine) as session:
        existing = session.exec(
            sa_select(func.count(LegacyOrder.id)).where(LegacyOrder.sku.like(f"{LEGACY_PREFIX}%"))
        ).one()[0] or 0
        missing = max(0, TOTAL_ROWS - int(existing))
        if missing == 0:
            logger.info("Legacy cricket dataset already present (%s rows)", existing)
            return 0

        now = datetime.utcnow()
        for idx in range(int(existing) + 1, TOTAL_ROWS + 1):
            product_name, variant, product_value, expected_weight = PRODUCTS[(idx - 1) % len(PRODUCTS)]
            reason_category, condition, reason_text, decision, risk_score = REASONS[(idx - 1) % len(REASONS)]
            customer = LegacyCustomer(
                name=f"Cricket Fan {idx}",
                email=f"cricket-legacy-{idx}@example.com",
                phone=f"+1-202-555-{(2000 + idx) % 10000:04d}",
                account_age_days=30 + (idx % 365),
                lifetime_orders=5 + (idx % 18),
                lifetime_returns=1 + (idx % 4),
                address=f"Cricket Avenue {idx}",
                device_id=f"cricket-legacy-device-{idx}",
            )
            session.add(customer)
            session.flush()

            order = LegacyOrder(
                customer_id=customer.id,
                sku=f"{LEGACY_PREFIX}{idx:04d}-{variant}",
                product_name=product_name,
                category="sports",
                product_value=product_value,
                expected_weight=expected_weight,
                payment_method="card",
                payment_method_risk_score=40 + (idx % 50),
                delivery_date=now - timedelta(days=2 + (idx % 12)),
                delivery_status="delivered",
            )
            session.add(order)
            session.flush()

            return_record = LegacyReturnRecord(
                order_id=order.id,
                customer_id=customer.id,
                return_reason=f"{reason_category}: {reason_text}",
                chat_transcript=f"Customer says the cricket ball order {order.sku} does not match the listing.",
                email_text=f"Please help with return for {order.sku}; OCR should match the cricket ball label.",
                returned_weight=expected_weight - 0.01,
                condition_reported=condition.lower(),
                return_date=now - timedelta(days=1 + (idx % 5)),
            )
            session.add(return_record)
            session.flush()

            score = LegacyFraudScore(
                return_id=return_record.id,
                rule_score=min(100, risk_score - 8),
                structured_ml_score=min(100, risk_score - 4),
                nlp_score=min(100, risk_score - 6),
                anomaly_score=min(100, risk_score - 2),
                final_score=risk_score,
                reason_codes_json=json.dumps(
                    ["CRICKET_PRODUCT", "OCR_EVIDENCE_EXPECTED", reason_category.replace(" ", "_").upper()]
                ),
                explanation=f"Cricket ball return seed {idx} created for OCR and case review.",
            )
            session.add(score)
            session.flush()

            case = LegacyReturnCase(
                return_id=return_record.id,
                risk_score=float(risk_score),
                risk_level=_legacy_case_score(idx)[1],
                decision=decision,
                status="OPEN",
                recommended_action="Review cricket-ball evidence and release refund after OCR check" if decision != "AUTO_APPROVE" else "Approve automatically",
                assigned_to="analyst.queue" if decision != "AUTO_APPROVE" else None,
            )
            session.add(case)

            if idx % 20 == 0:
                session.commit()
                logger.info("Seeded %s legacy cricket rows", idx)

        session.commit()
        logger.info("Seeded %s legacy cricket orders/returns/cases", missing)
        return missing


async def _get_or_create_merchant(session):
    result = await session.execute(sa_select(ProdMerchant).where(ProdMerchant.name == "Cricket Demo Merchant"))
    merchant = result.scalar_one_or_none()
    if merchant:
        return merchant
    merchant = ProdMerchant(name="Cricket Demo Merchant", industry="sports")
    session.add(merchant)
    await session.flush()
    return merchant


async def _prod_seed_rows() -> int:
    async with async_session_factory() as session:
        result = await session.execute(
            sa_select(func.count(ProdOrder.id)).where(ProdOrder.external_order_id.like(f"{PROD_PREFIX}%"))
        )
        existing = int(result.scalar() or 0)
        missing = max(0, TOTAL_ROWS - existing)
        if missing == 0:
            logger.info("Production cricket dataset already present (%s rows)", existing)
            return 0

        merchant = await _get_or_create_merchant(session)
        now = datetime.now(timezone.utc)
        for idx in range(existing + 1, TOTAL_ROWS + 1):
            product_name, variant, product_value, expected_weight = PRODUCTS[(idx - 1) % len(PRODUCTS)]
            reason_category, condition, reason_text, decision, risk_score = REASONS[(idx - 1) % len(REASONS)]
            email = f"cricket-prod-{idx}@example.com"
            customer = ProdCustomer(
                merchant_id=merchant.id,
                external_customer_id=f"cricket-prod-cust-{idx:04d}",
                name=f"Cricket Customer {idx}",
                email_hash=_hash(email),
                phone_hash=_hash(f"+1-303-555-{(3000 + idx) % 10000:04d}"),
                account_age_days=45 + (idx % 280),
                lifetime_orders=8 + (idx % 20),
                lifetime_returns=1 + (idx % 5),
                lifetime_refunds=0,
                customer_risk_score=min(95, 25 + (idx % 60)),
            )
            session.add(customer)
            await session.flush()

            order = ProdOrder(
                merchant_id=merchant.id,
                customer_id=customer.id,
                external_order_id=f"{PROD_PREFIX}{idx:04d}",
                sku=f"{PROD_PREFIX}{idx:04d}-{variant}",
                product_name=product_name,
                category="sports",
                product_value=product_value,
                quantity=1,
                payment_method="card",
                payment_method_risk_score=30 + (idx % 55),
                order_status="DELIVERED",
                order_date=now - timedelta(days=4 + (idx % 10)),
                delivery_date=now - timedelta(days=2 + (idx % 10)),
            )
            session.add(order)
            await session.flush()

            shipment = ProdShipment(
                merchant_id=merchant.id,
                order_id=order.id,
                carrier="FedEx",
                tracking_number_hash=_hash(f"TRACK-{idx:04d}"),
                delivery_status="DELIVERED",
                delivery_address_hash=_hash(f"delivery-address-{idx:04d}"),
                pickup_address_hash=_hash(f"pickup-address-{idx:04d}"),
                expected_weight=expected_weight,
                scanned_delivery_weight=expected_weight + 0.01,
                returned_weight=expected_weight - 0.01,
                weight_difference=0.01,
                delivery_confirmation_type="PHOTO",
                delivery_photo_url=f"https://example.com/cricket/{idx:04d}.jpg",
                warehouse_scan_status="MATCHED",
            )
            session.add(shipment)
            await session.flush()

            payment = ProdPayment(
                merchant_id=merchant.id,
                customer_id=customer.id,
                order_id=order.id,
                payment_method="card",
                payment_token_hash=_hash(f"payment-token-{idx:04d}"),
                amount=product_value,
                chargeback_flag=idx % 7 == 0,
                chargeback_date=now - timedelta(days=1) if idx % 7 == 0 else None,
            )
            session.add(payment)

            return_request = ProdReturnRequest(
                merchant_id=merchant.id,
                customer_id=customer.id,
                order_id=order.id,
                shipment_id=shipment.id,
                external_return_id=f"CR-RET-{idx:04d}",
                created_by="seed.cricket",
                return_reason_category=reason_category.replace(" ", "_").upper(),
                return_reason=f"{reason_category}: {reason_text}",
                detailed_description=f"Cricket ball {product_name.lower()} with visible seam wear and packaging mismatch.",
                condition_reported=condition.replace(" ", "_").upper(),
                return_method="PICKUP",
                pickup_address_id=f"pickup-address-{idx:04d}",
                preferred_refund_method="ORIGINAL_PAYMENT",
                return_status="REQUESTED",
                fraud_screening_status="PENDING",
                eligibility_override=False,
                return_channel="ORDER_PORTAL",
                return_date=now - timedelta(hours=6 + (idx % 12)),
                hours_after_delivery=float(24 + (idx % 48)),
            )
            session.add(return_request)
            await session.flush()

            return_item = ProdReturnItem(
                return_id=return_request.id,
                order_id=order.id,
                sku=order.sku,
                product_name=order.product_name,
                category=order.category,
                quantity=1,
                product_value=product_value,
                declared_condition=condition.replace(" ", "_").upper(),
                warehouse_condition="PENDING",
                item_match_status="PENDING",
            )
            session.add(return_item)

            support = ProdSupportInteraction(
                merchant_id=merchant.id,
                customer_id=customer.id,
                return_id=return_request.id,
                channel="chat",
                subject=f"Cricket ball return {idx:04d}",
                message_text=f"I uploaded a cricket ball photo for order {order.external_order_id}. The OCR should identify the cricket ball label and SKU.",
                sentiment_score=0.35,
                urgency_score=0.7,
            )
            session.add(support)

            final_score = risk_score
            risk_level = "HIGH" if final_score >= 70 else "MEDIUM" if final_score >= 40 else "LOW"
            fraud_score = ProdFraudScore(
                merchant_id=merchant.id,
                return_id=return_request.id,
                customer_id=customer.id,
                rule_score=min(100, final_score - 12),
                structured_ml_score=min(100, final_score - 8),
                nlp_score=min(100, final_score - 10),
                graph_score=min(100, final_score - 6),
                anomaly_score=min(100, final_score - 4),
                final_score=final_score,
                risk_level=risk_level,
                decision=decision,
                reason_codes_json=["CRICKET_PRODUCT", "OCR_EVIDENCE_EXPECTED", reason_category.replace(" ", "_").upper()],
                score_breakdown_json={
                    "rule_score": min(100, final_score - 12),
                    "structured_ml_score": min(100, final_score - 8),
                    "nlp_score": min(100, final_score - 10),
                    "graph_score": min(100, final_score - 6),
                    "anomaly_score": min(100, final_score - 4),
                },
            )
            session.add(fraud_score)
            await session.flush()

            fraud_case = ProdFraudCase(
                merchant_id=merchant.id,
                return_id=return_request.id,
                customer_id=customer.id,
                fraud_score_id=fraud_score.id,
                case_status="OPEN",
                priority="HIGH" if final_score >= 70 else "MEDIUM",
                assigned_to="analyst.queue",
                recommended_action="Review cricket-ball return evidence and OCR match before refunding",
                case_summary=f"Cricket ball return {idx:04d} needs OCR-backed verification.",
            )
            session.add(fraud_case)

            if idx % 20 == 0:
                await session.commit()
                logger.info("Seeded %s production cricket rows", idx)

        await session.commit()
        logger.info("Seeded %s production cricket orders/returns/cases", missing)
        return missing


def main() -> None:
    setup_logging()
    ensure_schema()
    legacy_added = _legacy_seed_rows()
    prod_added = asyncio.run(_prod_seed_rows())
    print({"legacy_added": legacy_added, "prod_added": prod_added})


if __name__ == "__main__":
    main()
