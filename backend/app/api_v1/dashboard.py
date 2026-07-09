from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.redis import get_redis, RedisClient
from app.services.dashboard_service import DashboardService

logger = logging.getLogger("returnshield.api.dashboard")
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/overview")
async def dashboard_overview(
    merchant_id: UUID,
    force_refresh: bool = False,
    session: AsyncSession = Depends(get_async_session),
    redis: RedisClient = Depends(get_redis),
):
    service = DashboardService(session, redis)
    data = await service.get_overview(merchant_id, force_refresh=force_refresh)
    return {"merchant_id": str(merchant_id), "data": data}


@router.get("/risk-distribution")
async def risk_distribution(
    merchant_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    redis: RedisClient = Depends(get_redis),
):
    service = DashboardService(session, redis)
    data = await service.get_risk_distribution(merchant_id)
    return {"merchant_id": str(merchant_id), "data": data}


@router.get("/recent-cases")
async def recent_cases(
    merchant_id: UUID,
    limit: int = 10,
    session: AsyncSession = Depends(get_async_session),
    redis: RedisClient = Depends(get_redis),
):
    service = DashboardService(session, redis)
    data = await service.get_recent_cases(merchant_id, limit=limit)
    return {"merchant_id": str(merchant_id), "data": data}


@router.post("/refresh-cache")
async def refresh_cache(
    merchant_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    redis: RedisClient = Depends(get_redis),
):
    service = DashboardService(session, redis)
    await service.invalidate_cache(merchant_id)
    return {"status": "cache_invalidated", "merchant_id": str(merchant_id)}
