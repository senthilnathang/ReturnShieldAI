from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_async_session
from ..prod_models.customer import Customer
from ..prod_models.merchant import Merchant
from ..prod_models.order import Order
from ..utils.product_images import product_image_data_uri
from ..prod_models.payment import Payment
from ..prod_models.shipment import Shipment

logger = logging.getLogger("returnshield.api.shop")
router = APIRouter(prefix="/shop", tags=["Shop"])

# Demo product catalog. Cricket products use PNG data URIs so OpenRouter vision can compare them directly.
_PRODUCTS: list[dict[str, Any]] = [
    {"id": "sku-h-1001", "name": "Aurora Wireless Headphones", "category": "electronics", "price": 129.0, "weight": 0.4, "tag": "Bestseller", "color": "#6366f1"},
    {"id": "sku-e-1002", "name": "Nimbus Mechanical Keyboard", "category": "electronics", "price": 89.0, "weight": 0.9, "tag": "", "color": "#0ea5e9"},
    {"id": "sku-e-1003", "name": "Pulse Smart Watch", "category": "electronics", "price": 199.0, "weight": 0.2, "tag": "New", "color": "#14b8a6"},
    {"id": "sku-e-1004", "name": "Vortex Phone 5G", "category": "electronics", "price": 699.0, "weight": 0.3, "tag": "Premium", "color": "#f59e0b"},
    {"id": "sku-a-2001", "name": "Cashmere Sweater", "category": "apparel", "price": 180.0, "weight": 0.6, "tag": "", "color": "#ef4444"},
    {"id": "sku-a-2002", "name": "Designer Jacket", "category": "apparel", "price": 420.0, "weight": 1.1, "tag": "Limited", "color": "#8b5cf6"},
    {"id": "sku-a-2003", "name": "Runner Sneakers", "category": "apparel", "price": 145.0, "weight": 0.8, "tag": "", "color": "#22c55e"},
    {"id": "sku-h-3001", "name": "Ceramic Coffee Mug", "category": "home", "price": 24.0, "weight": 0.5, "tag": "", "color": "#ec4899"},
    {"id": "sku-h-3002", "name": "Aroma Diffuser", "category": "home", "price": 59.0, "weight": 0.7, "tag": "New", "color": "#10b981"},
    {"id": "sku-s-4001", "name": "Cricket Ball - Red Leather", "category": "sports", "price": 24.99, "weight": 0.3, "tag": "", "color": "#dc2626"},
    {"id": "sku-s-4002", "name": "Yoga Mat Pro", "category": "sports", "price": 49.0, "weight": 1.2, "tag": "", "color": "#3b82f6"},
    {"id": "sku-s-4003", "name": "Insulated Water Bottle", "category": "sports", "price": 32.0, "weight": 0.4, "tag": "Eco", "color": "#06b6d4"},
]

_PRODUCT_BY_ID = {p["id"]: p for p in _PRODUCTS}


def _product_image(color: str, name: str) -> str:
    return product_image_data_uri(name, accent=color)


class ProductRead(BaseModel):
    id: str
    name: str
    category: str
    price: float
    weight: float
    tag: str
    image: str


class CartItem(BaseModel):
    product_id: str
    quantity: int = Field(ge=1)


class CheckoutRequest(BaseModel):
    customer_name: str
    customer_email: str
    customer_phone: Optional[str] = None
    address: Optional[str] = None
    payment_method: str = "card"
    items: list[CartItem]


class CheckoutOrderItem(BaseModel):
    order_id: UUID
    external_order_id: str
    sku: str
    product_name: str
    category: str
    product_value: float
    quantity: int
    order_status: str
    delivery_date: datetime
    product_image_url: str | None = None
    delivery_image_url: str | None = None


class CheckoutResponse(BaseModel):
    customer_id: UUID
    merchant_id: UUID
    payment_status: str
    transaction_id: str
    total: float
    orders: list[CheckoutOrderItem]


def _hash(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return hashlib.sha256(value.strip().encode("utf-8")).hexdigest()


async def _default_merchant_id(session: AsyncSession) -> UUID:
    row = (await session.execute(select(Merchant).order_by(Merchant.name).limit(1))).scalar_one_or_none()
    if row:
        return row.id
    raise HTTPException(status_code=500, detail="No merchant configured for the shop")


@router.get("/products", response_model=list[ProductRead])
async def list_products(category: Optional[str] = None):
    items = _PRODUCTS if not category else [p for p in _PRODUCTS if p["category"] == category]
    return [
        ProductRead(
            id=p["id"], name=p["name"], category=p["category"], price=p["price"],
            weight=p["weight"], tag=p["tag"], image=_product_image(p["color"], p["name"]),
        )
        for p in items
    ]


@router.get("/categories", response_model=list[str])
async def list_categories():
    return list(dict.fromkeys(p["category"] for p in _PRODUCTS))


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(payload: CheckoutRequest, session: AsyncSession = Depends(get_async_session)):
    if not payload.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    merchant_id = await _default_merchant_id(session)
    now = datetime.now(timezone.utc)
    # Demo: orders are marked delivered immediately so returns are testable right away.
    delivery_date = now - timedelta(hours=6)

    customer = Customer(
        merchant_id=merchant_id,
        external_customer_id=f"CUST-{customer_external_seq()}",
        name=payload.customer_name,
        email_hash=_hash(payload.customer_email),
        phone_hash=_hash(payload.customer_phone),
        account_age_days=120,
        lifetime_orders=len(payload.items),
    )
    session.add(customer)
    await session.flush()

    created_orders: list[CheckoutOrderItem] = []
    total = 0.0
    seq = order_external_seq()
    for item in payload.items:
        product = _PRODUCT_BY_ID.get(item.product_id)
        if not product:
            raise HTTPException(status_code=400, detail=f"Unknown product: {item.product_id}")
        ext_id = f"ORD-{seq}"
        seq += 1
        product_image_url = product_image_data_uri(product["name"], sku=product["id"], category=product["category"], accent=product["color"])
        order = Order(
            merchant_id=merchant_id,
            customer_id=customer.id,
            external_order_id=ext_id,
            sku=product["id"],
            product_name=product["name"],
            product_image_url=product_image_url,
            delivery_image_url=product_image_url,
            category=product["category"],
            product_value=product["price"],
            quantity=item.quantity,
            payment_method=payload.payment_method,
            payment_method_risk_score=10,
            order_status="DELIVERED",
            order_date=now - timedelta(days=1),
            delivery_date=delivery_date,
        )
        session.add(order)
        await session.flush()

        session.add(
            Shipment(
                merchant_id=merchant_id,
                order_id=order.id,
                carrier="Demo Logistics",
                tracking_number_hash=_hash(f"TRK-{ext_id}"),
                delivery_status="DELIVERED",
                expected_weight=product["weight"],
                scanned_delivery_weight=product["weight"],
            )
        )
        session.add(
            Payment(
                merchant_id=merchant_id,
                customer_id=customer.id,
                order_id=order.id,
                payment_method=payload.payment_method,
                card_bin="424242" if payload.payment_method == "card" else None,
                amount=product["price"] * item.quantity,
            )
        )
        total += product["price"] * item.quantity
        created_orders.append(
            CheckoutOrderItem(
                order_id=order.id, external_order_id=ext_id, sku=product["id"],
                product_name=product["name"], category=product["category"],
                product_value=product["price"], quantity=item.quantity,
                order_status="DELIVERED", delivery_date=delivery_date,
                product_image_url=product_image_url,
                delivery_image_url=product_image_url,
            )
        )

    await session.commit()

    return CheckoutResponse(
        customer_id=customer.id,
        merchant_id=merchant_id,
        payment_status="PAID",
        transaction_id=f"TXN-{int(now.timestamp())}",
        total=round(total, 2),
        orders=created_orders,
    )


@router.get("/customers/{customer_id}/orders", response_model=list[CheckoutOrderItem])
async def list_customer_orders(customer_id: UUID, session: AsyncSession = Depends(get_async_session)):
    rows = (
        await session.execute(
            select(Order).where(Order.customer_id == customer_id).order_by(Order.order_date.desc())
        )
    ).scalars().all()
    return [
        CheckoutOrderItem(
            order_id=o.id, external_order_id=o.external_order_id or str(o.id),
            sku=o.sku or "", product_name=o.product_name or "", category=o.category or "",
            product_value=float(o.product_value or 0), quantity=o.quantity,
            order_status=o.order_status or "UNKNOWN", delivery_date=o.delivery_date or datetime.now(timezone.utc),
            product_image_url=o.product_image_url,
            delivery_image_url=o.delivery_image_url,
        )
        for o in rows
    ]


# Simple monotonic sequence helpers (demo-only; collision-resistant enough for demo traffic).
_SEQ_CUST = [200000]
_SEQ_ORDER = [700000]


def customer_external_seq() -> int:
    _SEQ_CUST[0] += 1
    return _SEQ_CUST[0]


def order_external_seq() -> int:
    _SEQ_ORDER[0] += 1
    return _SEQ_ORDER[0]
