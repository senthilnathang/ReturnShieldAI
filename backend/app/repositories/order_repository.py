from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.prod_models.order import Order
from .base import BaseRepository


class OrderRepository(BaseRepository[Order]):
    def __init__(self, session: AsyncSession):
        super().__init__(Order, session)

    async def find_by_external_id(self, merchant_id: UUID, external_order_id: str) -> Optional[Order]:
        query = select(Order).where(
            Order.merchant_id == merchant_id,
            Order.external_order_id == external_order_id,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def find_or_create(
        self,
        merchant_id: UUID,
        customer_id: UUID,
        external_order_id: Optional[str] = None,
        **kwargs,
    ) -> Order:
        if external_order_id:
            existing = await self.find_by_external_id(merchant_id, external_order_id)
            if existing:
                return existing
        return await self.create(
            merchant_id=merchant_id,
            customer_id=customer_id,
            external_order_id=external_order_id,
            **kwargs,
        )

    async def list_by_customer(
        self, customer_id: UUID, skip: int = 0, limit: int = 50
    ) -> tuple[list[Order], int]:
        filters = {"customer_id": customer_id}
        return await self.list(skip=skip, limit=limit, order_by="order_date", descending=True, filters=filters)

    async def search(
        self,
        *,
        merchant_id: Optional[UUID] = None,
        customer_id: Optional[UUID] = None,
        category: Optional[str] = None,
        q: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Order], int]:
        query = select(Order)
        if merchant_id is not None:
            query = query.where(Order.merchant_id == merchant_id)
        if customer_id is not None:
            query = query.where(Order.customer_id == customer_id)
        if category:
            query = query.where(Order.category == category)
        if q:
            pattern = f"%{q}%"
            query = query.where(
                or_(
                    Order.external_order_id.ilike(pattern),
                    Order.sku.ilike(pattern),
                    Order.product_name.ilike(pattern),
                )
            )

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_query)).scalar() or 0

        query = query.order_by(Order.order_date.desc().nullslast()).offset(skip).limit(limit)
        result = await self.session.execute(query)
        items = list(result.scalars().all())
        return items, total

