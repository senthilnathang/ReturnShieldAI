from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_async_session
from app.core.redis import get_redis, RedisClient
from app.schemas.dashboard_schema import HealthResponse

logger = logging.getLogger("returnshield.api.health")
router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="ok")


@router.get("/health/postgres", response_model=HealthResponse)
async def health_postgres(session: AsyncSession = Depends(get_async_session)):
    try:
        await session.execute(text("SELECT 1"))
        postgres_status = "ok"
    except Exception as e:
        logger.error("Postgres health check failed: %s", e)
        postgres_status = f"error: {str(e)[:100]}"

    return HealthResponse(status="ok" if postgres_status == "ok" else "degraded", postgres=postgres_status)


@router.get("/health/redis", response_model=HealthResponse)
async def health_redis(redis: RedisClient = Depends(get_redis)):
    try:
        await redis.client.ping()
        redis_status = "ok"
    except Exception as e:
        logger.error("Redis health check failed: %s", e)
        redis_status = f"error: {str(e)[:100]}"

    return HealthResponse(status="ok" if redis_status == "ok" else "degraded", redis=redis_status)
