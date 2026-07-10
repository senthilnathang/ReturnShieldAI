from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_async_session
from ..prod_models.order import Order
from ..repositories.order_repository import OrderRepository
from ..schemas.order_schema import OrderRead

logger = logging.getLogger("returnshield.api.orders")
router = APIRouter(prefix="/orders", tags=["Orders"])


def _to_read(o: Order) -> OrderRead:
    return OrderRead(
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


@router.get("/stats", response_model=dict)
async def order_stats(
    merchant_id: UUID | None = None,
    session: AsyncSession = Depends(get_async_session),
):
    summary = select(
        func.count(Order.id),
        func.coalesce(func.sum(Order.product_value), 0),
        func.coalesce(func.avg(Order.product_value), 0),
    )
    if merchant_id is not None:
        summary = summary.where(Order.merchant_id == merchant_id)
    row = (await session.execute(summary)).one()
    total_count = row[0] or 0
    total_value = float(row[1] or 0)
    avg_value = float(row[2] or 0)

    cat_q = select(Order.category, func.count(Order.id)).where(Order.category.isnot(None))
    if merchant_id is not None:
        cat_q = cat_q.where(Order.merchant_id == merchant_id)
    cat_q = cat_q.group_by(Order.category).order_by(func.count(Order.id).desc()).limit(10)
    by_category = [
        {"category": c or "unknown", "count": n}
        for c, n in (await session.execute(cat_q)).all()
    ]

    method_q = select(Order.payment_method, func.count(Order.id)).where(Order.payment_method.isnot(None))
    if merchant_id is not None:
        method_q = method_q.where(Order.merchant_id == merchant_id)
    method_q = method_q.group_by(Order.payment_method).order_by(func.count(Order.id).desc()).limit(10)
    by_method = [
        {"method": m or "unknown", "count": n}
        for m, n in (await session.execute(method_q)).all()
    ]

    return {
        "total_orders": total_count,
        "total_value": round(total_value, 2),
        "avg_value": round(avg_value, 2),
        "by_category": by_category,
        "by_payment_method": by_method,
    }


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(
    order_id: UUID,
    session: AsyncSession = Depends(get_async_session),
):
    repo = OrderRepository(session)
    order = await repo.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return _to_read(order)


@router.get("", response_model=dict)
async def list_orders(
    customer_id: UUID | None = None,
    merchant_id: UUID | None = None,
    category: str | None = None,
    q: str | None = None,
    skip: int = 0,
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session),
):
    repo = OrderRepository(session)
    items, total = await repo.search(
        merchant_id=merchant_id,
        customer_id=customer_id,
        category=category,
        q=q,
        skip=skip,
        limit=limit,
    )
    return {
        "items": [_to_read(o) for o in items],
        "total": total,
        "page": skip // limit + 1 if limit > 0 else 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit if limit > 0 else 1,
    }
