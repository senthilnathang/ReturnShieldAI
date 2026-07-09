from __future__ import annotations

from httpx import AsyncClient, ASGITransport
import pytest


@pytest.mark.asyncio
async def test_production_health():
    from app.prod_main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_production_health_postgres():
    from app.prod_main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/health/postgres")
        # May fail if no postgres, but endpoint should exist
        assert resp.status_code in (200, 503)


@pytest.mark.asyncio
async def test_production_health_redis():
    from app.prod_main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/health/redis")
        # May fail if no redis, but endpoint should exist
        assert resp.status_code in (200, 503)
