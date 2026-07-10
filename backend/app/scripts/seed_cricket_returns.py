#!/usr/bin/env python3
"""Seed cricket-ball order demo data only.

This script keeps the cricket dataset to orders, customers, shipments, and
payments. It removes any previously seeded cricket returns, cases, or evidence
rows so users can create new returns manually from the Orders UI. The cricket
product images come from the shared PNG generator so vision comparisons work
in OpenRouter.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sqlalchemy import delete, func, select as sa_select
from sqlmodel import Session

from backend.app.core.database import async_session_factory, sync_engine
from backend.app.core.logging import setup_logging
from backend.app.db.base import Base as ProdBase
from backend.app.db.session import engine as legacy_engine
from backend.app.models import Customer as LegacyCustomer
from backend.app.models import FraudScore as LegacyFraudScore
from backend.app.models import Order as LegacyOrder
from backend.app.models import ReturnCase as LegacyReturnCase
from backend.app.models import ReturnRecord as LegacyReturnRecord
from backend.app.prod_models import Customer as ProdCustomer
from backend.app.prod_models import FraudCase as ProdFraudCase
from backend.app.prod_models import FraudScore as ProdFraudScore
from backend.app.prod_models import Merchant as ProdMerchant
from backend.app.prod_models import Order as ProdOrder
from backend.app.prod_models import Payment as ProdPayment
from backend.app.prod_models import ReturnItem as ProdReturnItem
from backend.app.prod_models import ReturnRequest as ProdReturnRequest
from backend.app.prod_models import Shipment as ProdShipment
from backend.app.prod_models import SupportInteraction as ProdSupportInteraction
from backend.app.utils.product_images import product_image_data_uri

logger = logging.getLogger("returnshield.scripts.seed_cricket_returns")
TARGET_ROWS = 100
LEGACY_PREFIX = "CRICKET-LEG-"
PROD_PREFIX = "CRICKET-PROD-"
CRICKET_MERCHANT_NAME = "Cricket Demo Merchant"

PRODUCTS = [
    ("Cricket Ball - Red Leather", "RED-LEATHER", 24.99, 0.156),
    ("Cricket Ball - White Leather", "WHITE-LEATHER", 26.49, 0.154),
    ("Cricket Ball - Practice Ball", "PRACTICE", 18.99, 0.148),
    ("Cricket Ball - Test Match", "TEST-MATCH", 29.99, 0.158),
    ("Cricket Ball - Limited Edition", "LIMITED", 34.99, 0.161),
]


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def ensure_schema() -> None:
    ProdBase.metadata.create_all(sync_engine)
    from sqlmodel import SQLModel

    SQLModel.metadata.create_all(legacy_engine)


def _cleanup_legacy_cricket_rows() -> int:
    with Session(legacy_engine) as session:
        order_ids = [
            row[0]
            for row in session.exec(sa_select(LegacyOrder.id).where(LegacyOrder.sku.like(f"{LEGACY_PREFIX}%"))).all()
        ]
        if not order_ids:
            return 0

        return_ids = [
            row[0]
            for row in session.exec(sa_select(LegacyReturnRecord.id).where(LegacyReturnRecord.order_id.in_(order_ids))).all()
        ]
        if return_ids:
            session.exec(delete(LegacyReturnCase).where(LegacyReturnCase.return_id.in_(return_ids)))
            session.exec(delete(LegacyFraudScore).where(LegacyFraudScore.return_id.in_(return_ids)))
            session.exec(delete(LegacyReturnRecord).where(LegacyReturnRecord.id.in_(return_ids)))
        session.exec(delete(LegacyOrder).where(LegacyOrder.id.in_(order_ids)))
        customer_ids = [
            row[0]
            for row in session.exec(sa_select(LegacyCustomer.id).where(LegacyCustomer.email.like("cricket-legacy-%"))).all()
        ]
        if customer_ids:
            session.exec(delete(LegacyCustomer).where(LegacyCustomer.id.in_(customer_ids)))
        session.commit()
        logger.info("Removed %s legacy cricket orders and related rows", len(order_ids))
        return len(order_ids)


async def _cleanup_prod_cricket_return_rows(session) -> int:
    order_ids = [
        row[0]
        for row in (await session.execute(sa_select(ProdOrder.id).where(ProdOrder.external_order_id.like(f"{PROD_PREFIX}%")))).all()
    ]
    if not order_ids:
        return 0

    return_ids = [
        row[0]
        for row in (await session.execute(sa_select(ProdReturnRequest.id).where(ProdReturnRequest.order_id.in_(order_ids)))).all()
    ]
    if return_ids:
        await session.execute(delete(ProdSupportInteraction).where(ProdSupportInteraction.return_id.in_(return_ids)))
        await session.execute(delete(ProdReturnItem).where(ProdReturnItem.return_id.in_(return_ids)))
        await session.execute(delete(ProdFraudCase).where(ProdFraudCase.return_id.in_(return_ids)))
        await session.execute(delete(ProdFraudScore).where(ProdFraudScore.return_id.in_(return_ids)))
        await session.execute(delete(ProdReturnRequest).where(ProdReturnRequest.id.in_(return_ids)))
    await session.commit()
    logger.info("Removed %s production cricket returns/cases", len(return_ids))
    return len(return_ids)


async def _get_or_create_merchant(session) -> ProdMerchant:
    result = await session.execute(sa_select(ProdMerchant).where(ProdMerchant.name == CRICKET_MERCHANT_NAME))
    merchant = result.scalar_one_or_none()
    if merchant:
        return merchant
    result = await session.execute(sa_select(ProdMerchant).limit(1))
    merchant = result.scalar_one_or_none()
    if merchant:
        return merchant
    merchant = ProdMerchant(name=CRICKET_MERCHANT_NAME, industry="sports")
    session.add(merchant)
    await session.flush()
    return merchant


async def _backfill_prod_order_images(session) -> int:
    result = await session.execute(sa_select(ProdOrder).where(ProdOrder.external_order_id.like(f"{PROD_PREFIX}%")))
    rows = result.scalars().all()
    updated = 0
    for order in rows:
        image_url = product_image_data_uri(order.product_name or order.sku or "Cricket Ball", sku=order.sku, category=order.category, accent="#dc2626")
        if order.product_image_url != image_url or order.delivery_image_url != image_url:
            order.product_image_url = image_url
            order.delivery_image_url = image_url
            updated += 1
    if updated:
        await session.commit()
    return updated


async def _seed_prod_orders() -> int:
    async with async_session_factory() as session:
        existing = int(
            (await session.execute(sa_select(func.count(ProdOrder.id)).where(ProdOrder.external_order_id.like(f"{PROD_PREFIX}%")))).scalar() or 0
        )
        missing = max(0, TARGET_ROWS - existing)
        merchant = await _get_or_create_merchant(session)
        backfilled = await _backfill_prod_order_images(session)
        if missing == 0:
            logger.info("Production cricket orders already present (%s rows); backfilled %s image rows", existing, backfilled)
            return 0

        if backfilled:
            logger.info("Backfilled %s cricket order image rows before seeding missing orders", backfilled)
        now = datetime.now(timezone.utc)
        for idx in range(existing + 1, TARGET_ROWS + 1):
            product_name, variant, product_value, expected_weight = PRODUCTS[(idx - 1) % len(PRODUCTS)]
            customer = ProdCustomer(
                merchant_id=merchant.id,
                external_customer_id=f"cricket-prod-cust-{idx:04d}",
                name=f"Cricket Customer {idx}",
                email_hash=_hash(f"cricket-prod-{idx}@example.com"),
                phone_hash=_hash(f"+1-303-555-{(3000 + idx) % 10000:04d}"),
                account_age_days=45 + (idx % 280),
                lifetime_orders=8 + (idx % 20),
                lifetime_returns=1 + (idx % 5),
                lifetime_refunds=0,
                customer_risk_score=min(95, 25 + (idx % 60)),
            )
            session.add(customer)
            await session.flush()

            product_image_url = product_image_data_uri(product_name, sku=f"{PROD_PREFIX}{idx:04d}-{variant}", category="sports", accent="#dc2626")
            order = ProdOrder(
                merchant_id=merchant.id,
                customer_id=customer.id,
                external_order_id=f"{PROD_PREFIX}{idx:04d}",
                sku=f"{PROD_PREFIX}{idx:04d}-{variant}",
                product_name=product_name,
                product_image_url=product_image_url,
                delivery_image_url=product_image_url,
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

            if idx % 20 == 0:
                await session.commit()
                logger.info("Seeded %s production cricket orders", idx)

        await session.commit()
        logger.info("Seeded %s production cricket orders", missing)
        return missing


async def main() -> None:
    setup_logging()
    ensure_schema()
    _cleanup_legacy_cricket_rows()
    async with async_session_factory() as session:
        await _cleanup_prod_cricket_return_rows(session)
    await _seed_prod_orders()


if __name__ == "__main__":
    asyncio.run(main())
