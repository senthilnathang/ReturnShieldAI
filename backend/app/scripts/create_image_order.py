#!/usr/bin/env python3
"""Create a demo order from a local image file.

This is intended for return testing: it stores the provided image as both the
product image and the delivery image so the return workflow can compare against
a known delivered reference.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import logging
import mimetypes
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sqlalchemy import select as sa_select

from backend.app.core.database import async_session_factory, sync_engine
from backend.app.core.logging import setup_logging
from backend.app.db.base import Base as ProdBase
from backend.app.prod_models.customer import Customer as ProdCustomer
from backend.app.prod_models.merchant import Merchant as ProdMerchant
from backend.app.prod_models.order import Order as ProdOrder
from backend.app.prod_models.payment import Payment as ProdPayment
from backend.app.prod_models.shipment import Shipment as ProdShipment

logger = logging.getLogger("returnshield.scripts.create_image_order")
DEFAULT_IMAGE_PATH = "/home/sibin/Downloads/prod_image.jpg"
DEFAULT_PRODUCT_NAME = "Custom Return Test Product"
DEFAULT_CATEGORY = "sports"
DEFAULT_SKU = "custom-return-test-001"
DEFAULT_PRICE = 24.99
DEFAULT_QUANTITY = 1
DEFAULT_MERCHANT_NAME = "Custom Image Test Merchant"
DEFAULT_CUSTOMER_NAME = "Image Test Customer"
DEFAULT_CUSTOMER_EMAIL = "image.test.customer@example.com"
DEFAULT_PHONE = "+91-90000-30000"


def ensure_schema() -> None:
    ProdBase.metadata.create_all(sync_engine)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _data_url_from_file(path: Path) -> tuple[str, str]:
    mime_type, _ = mimetypes.guess_type(path.name)
    if not mime_type:
        mime_type = "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{data}", mime_type


async def _get_or_create_merchant(session) -> ProdMerchant:
    result = await session.execute(sa_select(ProdMerchant).where(ProdMerchant.name == DEFAULT_MERCHANT_NAME))
    merchant = result.scalar_one_or_none()
    if merchant:
        return merchant
    result = await session.execute(sa_select(ProdMerchant).limit(1))
    merchant = result.scalar_one_or_none()
    if merchant:
        return merchant
    merchant = ProdMerchant(name=DEFAULT_MERCHANT_NAME, industry="sports")
    session.add(merchant)
    await session.flush()
    return merchant


async def create_order(image_path: Path, *, product_name: str, sku: str, category: str, price: float, quantity: int, customer_name: str, customer_email: str, phone: str) -> dict[str, Any]:
    if not image_path.exists():
        raise SystemExit(f"Image not found: {image_path}")
    image_data_url, mime_type = _data_url_from_file(image_path)
    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        merchant = await _get_or_create_merchant(session)
        customer = ProdCustomer(
            merchant_id=merchant.id,
            external_customer_id=f"custom-image-{int(now.timestamp())}",
            name=customer_name,
            email_hash=_hash(customer_email),
            phone_hash=_hash(phone),
            account_age_days=180,
            lifetime_orders=1,
            lifetime_returns=0,
            customer_risk_score=15,
        )
        session.add(customer)
        await session.flush()

        order = ProdOrder(
            merchant_id=merchant.id,
            customer_id=customer.id,
            external_order_id=f"CUSTOM-{now.strftime('%Y%m%d%H%M%S')}",
            sku=sku,
            product_name=product_name,
            product_image_url=image_data_url,
            delivery_image_url=image_data_url,
            category=category,
            product_value=price,
            quantity=quantity,
            payment_method="card",
            payment_method_risk_score=12,
            order_status="DELIVERED",
            order_date=now - timedelta(days=1),
            delivery_date=now - timedelta(hours=6),
        )
        session.add(order)
        await session.flush()

        session.add(
            ProdShipment(
                merchant_id=merchant.id,
                order_id=order.id,
                carrier="Demo Logistics",
                tracking_number_hash=_hash(f"TRACK-{order.external_order_id}"),
                delivery_status="DELIVERED",
                expected_weight=0.35,
                scanned_delivery_weight=0.35,
                returned_weight=0.35,
                weight_difference=0.0,
                delivery_confirmation_type="PHOTO",
                delivery_photo_url=str(image_path),
                warehouse_scan_status="MATCHED",
            )
        )
        session.add(
            ProdPayment(
                merchant_id=merchant.id,
                customer_id=customer.id,
                order_id=order.id,
                payment_method="card",
                payment_token_hash=_hash(f"payment-token-{order.external_order_id}"),
                amount=price * quantity,
                chargeback_flag=False,
            )
        )
        await session.commit()
        return {
            "merchant_id": str(merchant.id),
            "customer_id": str(customer.id),
            "order_id": str(order.id),
            "external_order_id": order.external_order_id,
            "product_name": product_name,
            "sku": sku,
            "category": category,
            "image_path": str(image_path),
            "mime_type": mime_type,
            "product_image_url": image_data_url,
            "delivery_image_url": image_data_url,
            "order_status": "DELIVERED",
            "delivery_date": order.delivery_date.isoformat() if order.delivery_date else None,
            "next_step": f"Create a return in the UI or call /api/v1/orders/{order.id}/returns",
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a custom demo order from a local image.")
    parser.add_argument("--image", default=DEFAULT_IMAGE_PATH, help="Path to the product image")
    parser.add_argument("--product-name", default=DEFAULT_PRODUCT_NAME, help="Product name to store on the order")
    parser.add_argument("--sku", default=DEFAULT_SKU, help="SKU to store on the order")
    parser.add_argument("--category", default=DEFAULT_CATEGORY, help="Order category")
    parser.add_argument("--price", type=float, default=DEFAULT_PRICE, help="Product price")
    parser.add_argument("--quantity", type=int, default=DEFAULT_QUANTITY, help="Order quantity")
    parser.add_argument("--customer-name", default=DEFAULT_CUSTOMER_NAME, help="Customer name")
    parser.add_argument("--customer-email", default=DEFAULT_CUSTOMER_EMAIL, help="Customer email")
    parser.add_argument("--customer-phone", default=DEFAULT_PHONE, help="Customer phone")
    args = parser.parse_args()

    setup_logging()
    ensure_schema()
    result = asyncio.run(
        create_order(
            Path(args.image).expanduser().resolve(),
            product_name=args.product_name,
            sku=args.sku,
            category=args.category,
            price=args.price,
            quantity=args.quantity,
            customer_name=args.customer_name,
            customer_email=args.customer_email,
            phone=args.customer_phone,
        )
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
