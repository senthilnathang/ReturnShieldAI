from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.prod_models.payment import Payment
from .base import BaseRepository


class PaymentRepository(BaseRepository[Payment]):
    def __init__(self, session: AsyncSession):
        super().__init__(Payment, session)

    async def search(
        self,
        *,
        merchant_id: Optional[UUID] = None,
        chargeback: Optional[bool] = None,
        q: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Payment], int]:
        query = select(Payment)
        if merchant_id is not None:
            query = query.where(Payment.merchant_id == merchant_id)
        if chargeback is not None:
            query = query.where(Payment.chargeback_flag == chargeback)
        if q:
            pattern = f"%{q}%"
            query = query.where(
                or_(
                    Payment.payment_method.ilike(pattern),
                    Payment.card_bin.ilike(pattern),
                    Payment.payment_token_hash.ilike(pattern),
                )
            )

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_query)).scalar() or 0

        query = query.order_by(Payment.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(query)
        items = list(result.scalars().all())
        return items, total
