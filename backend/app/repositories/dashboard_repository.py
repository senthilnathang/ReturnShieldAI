from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.prod_models.return_request import ReturnRequest
from backend.app.prod_models.fraud_score import FraudScore
from backend.app.prod_models.fraud_case import FraudCase


class DashboardRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_overview(self, merchant_id: UUID) -> dict:
        # Return counts
        return_count_query = select(func.count(ReturnRequest.id)).where(
            ReturnRequest.merchant_id == merchant_id
        )
        total_returns = (await self.session.execute(return_count_query)).scalar() or 0

        # Score-based aggregations
        score_query = select(
            func.count(FraudScore.id),
            func.sum(case((FraudScore.risk_level == "HIGH", 1), else_=0)),
            func.sum(case((FraudScore.decision == "MANUAL_REVIEW", 1), else_=0)),
            func.sum(case((FraudScore.decision == "AUTO_APPROVE", 1), else_=0)),
            func.avg(FraudScore.final_score),
        ).where(FraudScore.merchant_id == merchant_id)

        score_result = (await self.session.execute(score_query)).one()
        total_scored = score_result[0] or 0
        high_risk = score_result[1] or 0
        manual_review = score_result[2] or 0
        auto_approved = score_result[3] or 0
        avg_score = float(score_result[4] or 0)

        # Fraud prevented estimate
        avg_order_value_query = select(
            func.avg(ReturnRequest.order_id)  # placeholder — join orders for real value
        )

        fraud_prevented = high_risk * 100  # placeholder: $100 avg prevention per high-risk case

        return {
            "total_returns": total_returns,
            "total_scored": total_scored,
            "high_risk_cases": high_risk,
            "manual_review_cases": manual_review,
            "auto_approved_cases": auto_approved,
            "average_risk_score": round(avg_score, 1),
            "fraud_prevented_estimate": fraud_prevented,
        }

    async def get_risk_distribution(self, merchant_id: UUID) -> list[dict]:
        ranges = [
            ("0-19", (0, 19)),
            ("20-39", (20, 39)),
            ("40-59", (40, 59)),
            ("60-79", (60, 79)),
            ("80-100", (80, 100)),
        ]

        total_query = select(func.count(FraudScore.id)).where(
            FraudScore.merchant_id == merchant_id
        )
        total = (await self.session.execute(total_query)).scalar() or 1

        result = []
        for label, (low, high) in ranges:
            count_query = select(func.count(FraudScore.id)).where(
                FraudScore.merchant_id == merchant_id,
                FraudScore.final_score >= low,
                FraudScore.final_score <= high,
            )
            count = (await self.session.execute(count_query)).scalar() or 0
            result.append({
                "range": label,
                "count": count,
                "percentage": round(count / total * 100, 1),
            })

        return result

    async def get_recent_cases(self, merchant_id: UUID, limit: int = 10) -> list[dict]:
        from sqlalchemy.orm import joinedload

        query = (
            select(FraudCase)
            .options(joinedload(FraudCase.fraud_score))
            .where(FraudCase.merchant_id == merchant_id)
            .order_by(FraudCase.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        cases = result.unique().scalars().all()

        return [
            {
                "case_id": c.id,
                "return_id": c.return_id,
                "risk_score": c.fraud_score.final_score if c.fraud_score else 0,
                "risk_level": c.fraud_score.risk_level if c.fraud_score else "UNKNOWN",
                "decision": c.fraud_score.decision if c.fraud_score else "UNKNOWN",
                "case_status": c.case_status,
                "priority": c.priority,
                "created_at": c.created_at,
            }
            for c in cases
        ]
