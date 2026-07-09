from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import RedisClient
from app.repositories.dashboard_repository import DashboardRepository
from app.services.cache_service import CacheService

logger = logging.getLogger("returnshield.dashboard")


class DashboardService:
    def __init__(self, session: AsyncSession, redis: RedisClient):
        self.session = session
        self.repo = DashboardRepository(session)
        self.cache = CacheService(redis)

    async def get_overview(self, merchant_id: UUID, force_refresh: bool = False) -> dict[str, Any]:
        merchant_str = str(merchant_id)

        if not force_refresh:
            cached = await self.cache.get_dashboard_overview(merchant_str)
            if cached:
                return cached

        data = await self.repo.get_overview(merchant_id)
        await self.cache.set_dashboard_overview(merchant_str, data)
        return data

    async def get_risk_distribution(self, merchant_id: UUID) -> list[dict]:
        merchant_str = str(merchant_id)

        cached = await self.cache.get_risk_distribution(merchant_str)
        if cached:
            return cached

        data = await self.repo.get_risk_distribution(merchant_id)
        await self.cache.set_risk_distribution(merchant_str, data)
        return data

    async def get_recent_cases(self, merchant_id: UUID, limit: int = 10) -> list[dict]:
        return await self.repo.get_recent_cases(merchant_id, limit)

    async def invalidate_cache(self, merchant_id: UUID):
        await self.cache.invalidate_dashboard(str(merchant_id))
