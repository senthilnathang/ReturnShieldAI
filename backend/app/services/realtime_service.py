from __future__ import annotations

import json
import logging
from typing import Any, Optional
from uuid import UUID

from ..core.redis import RedisClient

logger = logging.getLogger("returnshield.realtime")


class RealtimeService:
    SCORING_STREAM = "returns:score:stream"
    SCORING_GROUP = "scoring-workers"

    def __init__(self, redis: RedisClient):
        self.redis = redis

    async def enqueue_scoring(self, return_id: UUID, merchant_id: UUID, customer_id: UUID):
        message = {
            "return_id": str(return_id),
            "merchant_id": str(merchant_id),
            "customer_id": str(customer_id),
            "created_at": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
        }
        await self.redis.stream_add(self.SCORING_STREAM, message)
        logger.info("Enqueued scoring for return %s", return_id)

    async def ensure_scoring_group(self):
        await self.redis.stream_create_group(self.SCORING_STREAM, self.SCORING_GROUP)

    async def consume_scoring_events(
        self, consumer: str, count: int = 10, block: int = 5000
    ) -> list[dict[str, Any]]:
        results = await self.redis.stream_read(
            self.SCORING_STREAM, self.SCORING_GROUP, consumer, count=count, block=block
        )

        events = []
        for stream_name, messages in results:
            for msg_id, msg_data in messages:
                events.append({
                    "id": msg_id,
                    "stream": stream_name,
                    "data": msg_data,
                })
        return events

    async def acknowledge_event(self, stream: str, message_id: str):
        await self.redis.stream_ack(stream, self.SCORING_GROUP, message_id)

    # --- Pub/Sub ---
    async def publish_fraud_case(self, case_id: UUID, merchant_id: UUID, risk_level: str):
        await self.redis.publish("fraud_cases:new", {
            "case_id": str(case_id),
            "merchant_id": str(merchant_id),
            "risk_level": risk_level,
            "timestamp": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
        })
        logger.info("Published fraud_case:new event for %s", case_id)

    async def publish_score_updated(self, return_id: UUID, score: int, merchant_id: UUID):
        await self.redis.publish("fraud_scores:updated", {
            "return_id": str(return_id),
            "score": score,
            "merchant_id": str(merchant_id),
        })

    async def request_dashboard_refresh(self, merchant_id: UUID):
        await self.redis.publish("dashboard:refresh", {
            "merchant_id": str(merchant_id),
        })
