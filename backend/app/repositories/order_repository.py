from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
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
