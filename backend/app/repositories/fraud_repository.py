from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.app.prod_models.fraud_score import FraudScore
from backend.app.prod_models.fraud_case import FraudCase
from backend.app.prod_models.analyst_feedback import AnalystFeedback
from app.repositories.base import BaseRepository


class FraudScoreRepository(BaseRepository[FraudScore]):
    def __init__(self, session: AsyncSession):
        super().__init__(FraudScore, session)


class FraudCaseRepository(BaseRepository[FraudCase]):
    def __init__(self, session: AsyncSession):
        super().__init__(FraudCase, session)

    async def get_with_score(self, case_id: UUID) -> Optional[FraudCase]:
        query = (
            select(FraudCase)
            .options(joinedload(FraudCase.fraud_score))
            .where(FraudCase.id == case_id)
        )
        result = await self.session.execute(query)
        return result.unique().scalar_one_or_none()

    async def get_case_counts_by_status(self, merchant_id: UUID) -> dict[str, int]:
        query = select(
            FraudCase.case_status,
            func.count(FraudCase.id),
        ).where(FraudCase.merchant_id == merchant_id).group_by(FraudCase.case_status)

        result = await self.session.execute(query)
        return {row[0]: row[1] for row in result.all()}

    async def get_recent_high_risk(self, merchant_id: UUID, limit: int = 10) -> list[FraudCase]:
        items, _ = await self.list(
            skip=0,
            limit=limit,
            order_by="created_at",
            descending=True,
            filters={"merchant_id": merchant_id, "case_status": "OPEN"},
        )
        return items


class AnalystFeedbackRepository(BaseRepository[AnalystFeedback]):
    def __init__(self, session: AsyncSession):
        super().__init__(AnalystFeedback, session)
