from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.app.prod_models.return_request import ReturnRequest
from backend.app.prod_models.return_item import ReturnItem
from backend.app.prod_models.support_interaction import SupportInteraction
from .base import BaseRepository


class ReturnRepository(BaseRepository[ReturnRequest]):
    def __init__(self, session: AsyncSession):
        super().__init__(ReturnRequest, session)

    async def get_with_relations(self, return_id: UUID) -> Optional[ReturnRequest]:
        query = (
            select(ReturnRequest)
            .options(
                joinedload(ReturnRequest.items),
                joinedload(ReturnRequest.support_interactions),
                joinedload(ReturnRequest.shipment),
                joinedload(ReturnRequest.order),
            )
            .where(ReturnRequest.id == return_id)
        )
        result = await self.session.execute(query)
        return result.unique().scalar_one_or_none()

    async def get_return_stats_for_customer(
        self, customer_id: UUID, merchant_id: UUID, days: int = 90
    ) -> dict:
        from datetime import datetime, timedelta, timezone

        since = datetime.now(timezone.utc) - timedelta(days=days)

        count_query = select(func.count(ReturnRequest.id)).where(
            ReturnRequest.customer_id == customer_id,
            ReturnRequest.merchant_id == merchant_id,
            ReturnRequest.created_at >= since,
        )
        count = (await self.session.execute(count_query)).scalar() or 0

        return {
            "return_count_90d": count,
            "customer_id": str(customer_id),
        }


class ReturnItemRepository(BaseRepository[ReturnItem]):
    def __init__(self, session: AsyncSession):
        super().__init__(ReturnItem, session)
