from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.database import get_async_session
from app.core.redis import get_redis, RedisClient
from backend.app.prod_models.fraud_case import FraudCase
from backend.app.prod_models.fraud_score import FraudScore
from app.repositories.fraud_repository import FraudCaseRepository
from app.schemas.fraud_schema import FraudCaseRead, FraudCaseStatusUpdate

logger = logging.getLogger("returnshield.api.fraud_cases")
router = APIRouter(prefix="/fraud-cases", tags=["Fraud Cases"])


@router.get("", response_model=dict)
async def list_fraud_cases(
    merchant_id: UUID,
    case_status: str | None = None,
    risk_level: str | None = None,
    skip: int = 0,
    limit: int = 50,
    session: AsyncSession = Depends(get_async_session),
):
    filters = {"merchant_id": merchant_id}
    if case_status:
        filters["case_status"] = case_status
    if risk_level:
        filters["risk_level"] = risk_level

    repo = FraudCaseRepository(session)
    items, total = await repo.list(
        skip=skip, limit=limit,
        order_by="created_at", descending=True,
        filters=filters,
    )
    return {
        "items": [
            FraudCaseRead(
                id=c.id,
                merchant_id=c.merchant_id,
                return_id=c.return_id,
                customer_id=c.customer_id,
                fraud_score_id=c.fraud_score_id,
                case_status=c.case_status,
                priority=c.priority,
                assigned_to=c.assigned_to,
                recommended_action=c.recommended_action,
                case_summary=c.case_summary,
                created_at=c.created_at,
                updated_at=c.updated_at,
                closed_at=c.closed_at,
            )
            for c in items
        ],
        "total": total,
        "page": skip // limit + 1 if limit > 0 else 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit if limit > 0 else 1,
    }


@router.get("/{case_id}", response_model=FraudCaseRead)
async def get_fraud_case(
    case_id: UUID,
    session: AsyncSession = Depends(get_async_session),
):
    repo = FraudCaseRepository(session)
    case = await repo.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Fraud case not found")
    return FraudCaseRead(
        id=case.id,
        merchant_id=case.merchant_id,
        return_id=case.return_id,
        customer_id=case.customer_id,
        fraud_score_id=case.fraud_score_id,
        case_status=case.case_status,
        priority=case.priority,
        assigned_to=case.assigned_to,
        recommended_action=case.recommended_action,
        case_summary=case.case_summary,
        created_at=case.created_at,
        updated_at=case.updated_at,
        closed_at=case.closed_at,
    )


@router.patch("/{case_id}/status", response_model=FraudCaseRead)
async def update_case_status(
    case_id: UUID,
    payload: FraudCaseStatusUpdate,
    session: AsyncSession = Depends(get_async_session),
    redis: RedisClient = Depends(get_redis),
):
    repo = FraudCaseRepository(session)
    update_data = payload.model_dump(exclude_none=True)
    case = await repo.update(case_id, **update_data)
    if not case:
        raise HTTPException(status_code=404, detail="Fraud case not found")

    # Publish dashboard refresh
    from app.services.realtime_service import RealtimeService
    realtime = RealtimeService(redis)
    await realtime.request_dashboard_refresh(case.merchant_id)

    return FraudCaseRead(
        id=case.id,
        merchant_id=case.merchant_id,
        return_id=case.return_id,
        customer_id=case.customer_id,
        fraud_score_id=case.fraud_score_id,
        case_status=case.case_status,
        priority=case.priority,
        assigned_to=case.assigned_to,
        recommended_action=case.recommended_action,
        case_summary=case.case_summary,
        created_at=case.created_at,
        updated_at=case.updated_at,
        closed_at=case.closed_at,
    )
