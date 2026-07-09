from __future__ import annotations

import pytest
from uuid import uuid4

from app.services.dashboard_service import DashboardService
from app.core.redis import RedisClient


@pytest.mark.asyncio
async def test_dashboard_overview(db_session):
    merchant_id = uuid4()

    # Mock Redis
    redis = RedisClient()
    service = DashboardService(db_session, redis)

    overview = await service.get_overview(merchant_id)
    assert isinstance(overview, dict)
    assert "total_returns" in overview
    assert "high_risk_cases" in overview


@pytest.mark.asyncio
async def test_dashboard_cache_invalidation(db_session):
    merchant_id = uuid4()
    redis = RedisClient()
    service = DashboardService(db_session, redis)

    await service.invalidate_cache(merchant_id)
    # No exception means success
    assert True
