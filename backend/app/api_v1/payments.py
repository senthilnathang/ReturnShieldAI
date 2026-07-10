from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_async_session
from ..prod_models.payment import Payment
from ..repositories.payment_repository import PaymentRepository
from ..schemas.payment_schema import PaymentRead

logger = logging.getLogger("returnshield.api.payments")
router = APIRouter(prefix="/payments", tags=["Payments"])


def _to_read(p: Payment) -> PaymentRead:
    return PaymentRead(
        id=p.id,
        merchant_id=p.merchant_id,
        customer_id=p.customer_id,
        order_id=p.order_id,
        payment_method=p.payment_method,
        payment_token_hash=p.payment_token_hash,
        upi_hash=p.upi_hash,
        card_bin=p.card_bin,
        amount=p.amount,
        chargeback_flag=p.chargeback_flag,
        chargeback_date=p.chargeback_date,
        created_at=p.created_at,
    )


@router.get("", response_model=dict)
async def list_payments(
    merchant_id: UUID | None = None,
    chargeback: bool | None = None,
    q: str | None = None,
    skip: int = 0,
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session),
):
    repo = PaymentRepository(session)
    items, total = await repo.search(
        merchant_id=merchant_id, chargeback=chargeback, q=q, skip=skip, limit=limit
    )
    return {
        "items": [_to_read(p) for p in items],
        "total": total,
        "page": skip // limit + 1 if limit > 0 else 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit if limit > 0 else 1,
    }


@router.get("/stats", response_model=dict)
async def payment_stats(
    merchant_id: UUID | None = None,
    session: AsyncSession = Depends(get_async_session),
):
    base = select(Payment)
    if merchant_id is not None:
        base = base.where(Payment.merchant_id == merchant_id)

    summary = select(
        func.count(Payment.id),
        func.coalesce(func.sum(Payment.amount), 0),
        func.sum(case((Payment.chargeback_flag.is_(True), 1), else_=0)),
    )
    if merchant_id is not None:
        summary = summary.where(Payment.merchant_id == merchant_id)
    row = (await session.execute(summary)).one()
    total_count = row[0] or 0
    total_amount = float(row[1] or 0)
    chargeback_count = row[2] or 0

    method_q = (
        select(Payment.payment_method, func.count(Payment.id))
        .where(Payment.payment_method.isnot(None))
    )
    if merchant_id is not None:
        method_q = method_q.where(Payment.merchant_id == merchant_id)
    method_q = method_q.group_by(Payment.payment_method).order_by(func.count(Payment.id).desc()).limit(10)
    by_method = [
        {"method": m or "unknown", "count": c}
        for m, c in (await session.execute(method_q)).all()
    ]

    return {
        "total_payments": total_count,
        "total_amount": round(total_amount, 2),
        "chargeback_count": chargeback_count,
        "chargeback_rate": round(chargeback_count / total_count * 100, 2) if total_count else 0.0,
        "by_method": by_method,
    }


@router.get("/{payment_id}", response_model=PaymentRead)
async def get_payment(
    payment_id: UUID,
    session: AsyncSession = Depends(get_async_session),
):
    repo = PaymentRepository(session)
    payment = await repo.get(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return _to_read(payment)
