from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_async_session
from ..repositories.order_repository import OrderRepository
from ..schemas.order_schema import OrderRead

logger = logging.getLogger("returnshield.api.orders")
router = APIRouter(prefix="/orders", tags=["Orders"])


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(
    order_id: UUID,
    session: AsyncSession = Depends(get_async_session),
):
    repo = OrderRepository(session)
    order = await repo.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return OrderRead(
        id=order.id,
        merchant_id=order.merchant_id,
        customer_id=order.customer_id,
        external_order_id=order.external_order_id,
        sku=order.sku,
        product_name=order.product_name,
        category=order.category,
        product_value=order.product_value,
        quantity=order.quantity,
        payment_method=order.payment_method,
        payment_method_risk_score=order.payment_method_risk_score,
        order_status=order.order_status,
        order_date=order.order_date,
        delivery_date=order.delivery_date,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


@router.get("", response_model=dict)
async def list_orders(
    customer_id: UUID,
    skip: int = 0,
    limit: int = 50,
    session: AsyncSession = Depends(get_async_session),
):
    repo = OrderRepository(session)
    items, total = await repo.list_by_customer(customer_id, skip=skip, limit=limit)
    return {
        "items": [
            OrderRead(
                id=o.id,
                merchant_id=o.merchant_id,
                customer_id=o.customer_id,
                external_order_id=o.external_order_id,
                sku=o.sku,
                product_name=o.product_name,
                category=o.category,
                product_value=o.product_value,
                quantity=o.quantity,
                payment_method=o.payment_method,
                payment_method_risk_score=o.payment_method_risk_score,
                order_status=o.order_status,
                order_date=o.order_date,
                delivery_date=o.delivery_date,
                created_at=o.created_at,
                updated_at=o.updated_at,
            )
            for o in items
        ],
        "total": total,
        "page": skip // limit + 1 if limit > 0 else 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit if limit > 0 else 1,
    }
