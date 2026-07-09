from __future__ import annotations

import logging
from typing import Any, Optional

from app.core.redis import RedisClient

logger = logging.getLogger("returnshield.cache")


class CacheService:
    def __init__(self, redis: RedisClient):
        self.redis = redis

    async def get_dashboard_overview(self, merchant_id: str) -> Optional[dict[str, Any]]:
        key = f"dashboard:merchant:{merchant_id}:overview"
        return await self.redis.cache_get_json(key)

    async def set_dashboard_overview(self, merchant_id: str, data: dict[str, Any], ttl: int = 60):
        key = f"dashboard:merchant:{merchant_id}:overview"
        await self.redis.cache_set_json(key, data, ttl)
        logger.debug("Cached dashboard overview for merchant %s", merchant_id)

    async def invalidate_dashboard(self, merchant_id: str):
        keys = [
            f"dashboard:merchant:{merchant_id}:overview",
            f"dashboard:merchant:{merchant_id}:risk_distribution",
            f"dashboard:merchant:{merchant_id}:case_counts",
        ]
        for key in keys:
            await self.redis.cache_delete(key)
        logger.debug("Invalidated dashboard cache for merchant %s", merchant_id)

    async def get_risk_distribution(self, merchant_id: str) -> Optional[list[dict]]:
        key = f"dashboard:merchant:{merchant_id}:risk_distribution"
        return await self.redis.cache_get_json(key)

    async def set_risk_distribution(self, merchant_id: str, data: list[dict], ttl: int = 120):
        key = f"dashboard:merchant:{merchant_id}:risk_distribution"
        await self.redis.cache_set_json(key, data, ttl)

    async def get_customer_features(self, customer_id: str) -> Optional[dict[str, Any]]:
        key = f"features:customer:{customer_id}:return_stats"
        return await self.redis.cache_get_json(key)

    async def set_customer_features(self, customer_id: str, data: dict[str, Any], ttl: int = 300):
        key = f"features:customer:{customer_id}:return_stats"
        await self.redis.cache_set_json(key, data, ttl)

    async def get_identity_linked(self, identity_hash: str) -> Optional[list[str]]:
        key = f"features:identity:{identity_hash}:linked_customers"
        return await self.redis.cache_get_json(key)

    async def set_identity_linked(self, identity_hash: str, data: list[str], ttl: int = 600):
        key = f"features:identity:{identity_hash}:linked_customers"
        await self.redis.cache_set_json(key, data, ttl)
