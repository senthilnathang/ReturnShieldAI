from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.database import get_async_session
from app.core.redis import get_redis, RedisClient
from backend.app.prod_models.return_request import ReturnRequest
from app.repositories.return_repository import ReturnRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.order_repository import OrderRepository
from app.services.realtime_service import RealtimeService
from app.services.scoring_stub_service import ScoringStubService
from app.schemas.return_schema import ReturnRequestCreate, ReturnRequestRead, EnqueueScoreRequest, ScoringResult

logger = logging.getLogger("returnshield.api.returns")
router = APIRouter(prefix="/returns", tags=["Returns"])


@router.post("", response_model=ReturnRequestRead, status_code=201)
async def create_return(
    payload: ReturnRequestCreate,
    session: AsyncSession = Depends(get_async_session),
):
    repo = ReturnRepository(session)
    return_req = await repo.create(**payload.model_dump())
    logger.info("Return %s created for customer %s", return_req.id, payload.customer_id)
    return ReturnRequestRead(
        id=return_req.id,
        merchant_id=return_req.merchant_id,
        customer_id=return_req.customer_id,
        order_id=return_req.order_id,
        shipment_id=return_req.shipment_id,
        external_return_id=return_req.external_return_id,
        return_reason=return_req.return_reason,
        condition_reported=return_req.condition_reported,
        return_status=return_req.return_status,
        return_channel=return_req.return_channel,
        return_date=return_req.return_date,
        hours_after_delivery=return_req.hours_after_delivery,
        created_at=return_req.created_at,
        updated_at=return_req.updated_at,
    )


@router.get("", response_model=dict)
async def list_returns(
    merchant_id: UUID,
    skip: int = 0,
    limit: int = 50,
    session: AsyncSession = Depends(get_async_session),
):
    repo = ReturnRepository(session)
    items, total = await repo.list(
        skip=skip, limit=limit,
        order_by="created_at", descending=True,
        filters={"merchant_id": merchant_id},
    )
    return {
        "items": [
            ReturnRequestRead(
                id=r.id,
                merchant_id=r.merchant_id,
                customer_id=r.customer_id,
                order_id=r.order_id,
                shipment_id=r.shipment_id,
                external_return_id=r.external_return_id,
                return_reason=r.return_reason,
                condition_reported=r.condition_reported,
                return_status=r.return_status,
                return_channel=r.return_channel,
                return_date=r.return_date,
                hours_after_delivery=r.hours_after_delivery,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in items
        ],
        "total": total,
        "page": skip // limit + 1 if limit > 0 else 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit if limit > 0 else 1,
    }


@router.get("/{return_id}", response_model=ReturnRequestRead)
async def get_return(
    return_id: UUID,
    session: AsyncSession = Depends(get_async_session),
):
    repo = ReturnRepository(session)
    return_req = await repo.get(return_id)
    if not return_req:
        raise HTTPException(status_code=404, detail="Return not found")
    return ReturnRequestRead(
        id=return_req.id,
        merchant_id=return_req.merchant_id,
        customer_id=return_req.customer_id,
        order_id=return_req.order_id,
        shipment_id=return_req.shipment_id,
        external_return_id=return_req.external_return_id,
        return_reason=return_req.return_reason,
        condition_reported=return_req.condition_reported,
        return_status=return_req.return_status,
        return_channel=return_req.return_channel,
        return_date=return_req.return_date,
        hours_after_delivery=return_req.hours_after_delivery,
        created_at=return_req.created_at,
        updated_at=return_req.updated_at,
    )


@router.post("/{return_id}/enqueue-score", response_model=dict)
async def enqueue_score(
    return_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    redis: RedisClient = Depends(get_redis),
):
    return_req = await session.get(ReturnRequest, return_id)
    if not return_req:
        raise HTTPException(status_code=404, detail="Return not found")

    realtime = RealtimeService(redis)
    await realtime.enqueue_scoring(return_id, return_req.merchant_id, return_req.customer_id)

    return {"status": "enqueued", "return_id": str(return_id)}


@router.post("/{return_id}/score-stub", response_model=ScoringResult)
async def score_stub(
    return_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    redis: RedisClient = Depends(get_redis),
):
    scoring = ScoringStubService(session)
    result = await scoring.score_return(return_id)
    score_record, fraud_case = await scoring.save_score_and_case(return_id, result)

    # Publish events
    realtime = RealtimeService(redis)
    await realtime.publish_score_updated(return_id, result.final_score, score_record.merchant_id)
    if fraud_case:
        await realtime.publish_fraud_case(fraud_case.id, fraud_case.merchant_id, result.risk_level)
    await realtime.request_dashboard_refresh(score_record.merchant_id)

    return result
