from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_async_session
from ..core.redis import get_redis, RedisClient
from ..prod_models.return_request import ReturnRequest
from ..repositories.return_repository import ReturnRepository
from ..schemas.return_schema import (
    ReturnRequestCreate,
    ReturnRequestRead,
    EnqueueScoreRequest,
    ScoringResult,
    ReturnDetailRead,
)
from ..services.realtime_service import RealtimeService
from ..services.scoring_stub_service import ScoringStubService
from ..services.return_service import ReturnService, ReturnValidationError

logger = logging.getLogger("returnshield.api.returns")
router = APIRouter(prefix="/returns", tags=["Returns"])


def _to_read(r: ReturnRequest) -> ReturnRequestRead:
    return ReturnRequestRead(
        id=r.id,
        merchant_id=r.merchant_id,
        customer_id=r.customer_id,
        order_id=r.order_id,
        shipment_id=r.shipment_id,
        external_return_id=r.external_return_id,
        created_by=r.created_by,
        return_reason_category=r.return_reason_category,
        return_reason=r.return_reason,
        detailed_description=r.detailed_description,
        condition_reported=r.condition_reported,
        return_method=r.return_method,
        pickup_address_id=r.pickup_address_id,
        preferred_refund_method=r.preferred_refund_method,
        return_status=r.return_status,
        fraud_screening_status=r.fraud_screening_status,
        eligibility_override=bool(r.eligibility_override),
        eligibility_override_reason=r.eligibility_override_reason,
        return_channel=r.return_channel,
        return_date=r.return_date,
        hours_after_delivery=r.hours_after_delivery,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


@router.post("", response_model=ReturnRequestRead, status_code=201)
async def create_return(
    payload: ReturnRequestCreate,
    session: AsyncSession = Depends(get_async_session),
):
    repo = ReturnRepository(session)
    return_req = await repo.create(**payload.model_dump())
    logger.info("Return %s created for customer %s", return_req.id, payload.customer_id)
    return _to_read(return_req)


@router.get("", response_model=dict)
async def list_returns(
    merchant_id: UUID | None = None,
    status: str | None = None,
    q: str | None = None,
    skip: int = 0,
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session),
):
    repo = ReturnRepository(session)
    items, total = await repo.search(
        merchant_id=merchant_id, status=status, q=q, skip=skip, limit=limit
    )
    return {
        "items": [_to_read(r).model_dump(mode="json") for r in items],
        "total": total,
        "page": skip // limit + 1 if limit > 0 else 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit if limit > 0 else 1,
    }


@router.get("/stats", response_model=dict)
async def return_stats(
    merchant_id: UUID | None = None,
    session: AsyncSession = Depends(get_async_session),
):
    summary = select(
        func.count(ReturnRequest.id),
        func.coalesce(func.avg(ReturnRequest.hours_after_delivery), 0),
    )
    if merchant_id is not None:
        summary = summary.where(ReturnRequest.merchant_id == merchant_id)
    row = (await session.execute(summary)).one()
    total_count = row[0] or 0
    avg_hours = float(row[1] or 0)

    status_q = select(ReturnRequest.return_status, func.count(ReturnRequest.id)).where(
        ReturnRequest.return_status.isnot(None)
    )
    if merchant_id is not None:
        status_q = status_q.where(ReturnRequest.merchant_id == merchant_id)
    status_q = status_q.group_by(ReturnRequest.return_status).order_by(func.count(ReturnRequest.id).desc()).limit(15)
    by_status = [
        {"status": s or "unknown", "count": n}
        for s, n in (await session.execute(status_q)).all()
    ]

    reason_q = select(ReturnRequest.return_reason, func.count(ReturnRequest.id)).where(
        ReturnRequest.return_reason.isnot(None)
    )
    if merchant_id is not None:
        reason_q = reason_q.where(ReturnRequest.merchant_id == merchant_id)
    reason_q = reason_q.group_by(ReturnRequest.return_reason).order_by(func.count(ReturnRequest.id).desc()).limit(10)
    top_reasons = [
        {"reason": (r or "unknown")[:120], "count": n}
        for r, n in (await session.execute(reason_q)).all()
    ]

    return {
        "total_returns": total_count,
        "avg_hours_after_delivery": round(avg_hours, 2),
        "by_status": by_status,
        "top_reasons": top_reasons,
    }


@router.get("/{return_id}", response_model=ReturnDetailRead)
async def get_return(
    return_id: UUID,
    session: AsyncSession = Depends(get_async_session),
):
    service = ReturnService(session)
    try:
        return await service.get_return_detail(return_id)
    except ReturnValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}) from exc


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
    await realtime.enqueue_scoring(return_id, return_req.merchant_id, return_req.customer_id, return_req.order_id)

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
