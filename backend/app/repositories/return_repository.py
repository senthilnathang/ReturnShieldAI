from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.app.prod_models.return_request import ReturnRequest
from backend.app.prod_models.return_item import ReturnItem
from backend.app.prod_models.support_interaction import SupportInteraction
from .base import BaseRepository


class ReturnRepository(BaseRepository[ReturnRequest]):
    def __init__(self, session: AsyncSession):
        super().__init__(ReturnRequest, session)

    async def search(
        self,
        *,
        merchant_id: Optional[UUID] = None,
        status: Optional[str] = None,
        q: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[ReturnRequest], int]:
        query = select(ReturnRequest)
        if merchant_id is not None:
            query = query.where(ReturnRequest.merchant_id == merchant_id)
        if status:
            query = query.where(ReturnRequest.return_status == status)
        if q:
            pattern = f"%{q}%"
            query = query.where(
                or_(
                    ReturnRequest.return_reason.ilike(pattern),
                    ReturnRequest.external_return_id.ilike(pattern),
                    ReturnRequest.condition_reported.ilike(pattern),
                )
            )

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_query)).scalar() or 0

        query = query.order_by(ReturnRequest.return_date.desc().nullslast()).offset(skip).limit(limit)
        result = await self.session.execute(query)
        items = list(result.scalars().all())
        return items, total

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
