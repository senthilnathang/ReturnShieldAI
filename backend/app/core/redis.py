from __future__ import annotations

import json
from typing import Any, Optional

import redis.asyncio as aioredis

from .config import settings


class RedisClient:
    def __init__(self):
        self._client: Optional[aioredis.Redis] = None

    async def initialize(self):
        if self._client is None:
            self._client = await aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
            )
            await self._client.ping()

    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None

    @property
    def client(self) -> aioredis.Redis:
        if self._client is None:
            raise RuntimeError("Redis client not initialized. Call initialize() first.")
        return self._client

    # --- Cache ---
    async def cache_get(self, key: str) -> Optional[str]:
        return await self.client.get(key)

    async def cache_set(self, key: str, value: str, ttl: int = 60):
        await self.client.setex(key, ttl, value)

    async def cache_delete(self, key: str):
        await self.client.delete(key)

    async def cache_get_json(self, key: str) -> Optional[Any]:
        val = await self.cache_get(key)
        return json.loads(val) if val else None

    async def cache_set_json(self, key: str, value: Any, ttl: int = 60):
        await self.cache_set(key, json.dumps(value, default=str), ttl)

    # --- Streams ---
    async def stream_add(self, stream: str, message: dict[str, Any], maxlen: int = 100_000):
        await self.client.xadd(stream, message, maxlen=maxlen)

    async def stream_read(self, stream: str, group: str, consumer: str, count: int = 10, block: int = 5000):
        return await self.client.xreadgroup(group, consumer, {stream: ">"}, count=count, block=block)

    async def stream_create_group(self, stream: str, group: str):
        try:
            await self.client.xgroup_create(stream, group, id="0", mkstream=True)
        except aioredis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def stream_ack(self, stream: str, group: str, message_id: str):
        await self.client.xack(stream, group, message_id)

    # --- Pub/Sub ---
    async def publish(self, channel: str, message: dict[str, Any]):
        await self.client.publish(channel, json.dumps(message, default=str))

    async def subscriber(self) -> aioredis.Redis:
        return self.client

    # --- Rate Limiting ---
    async def rate_limit_check(self, key: str, max_requests: int, window_seconds: int) -> bool:
        now = __import__("time").time()
        pipe = self.client.pipeline()
        pipe.zadd(key, {str(now): now})
        pipe.zremrangebyscore(key, 0, now - window_seconds)
        pipe.zcard(key)
        pipe.expire(key, window_seconds + 1)
        _, _, count, _ = await pipe.execute()
        return count <= max_requests

    async def rate_limit_remaining(self, key: str, max_requests: int, window_seconds: int) -> int:
        count = await self.client.zcard(key)
        return max(0, max_requests - count)


redis_client = RedisClient()


async def get_redis() -> RedisClient:
    if redis_client._client is None:
        await redis_client.initialize()
    return redis_client
