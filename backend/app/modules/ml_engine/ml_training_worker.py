from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from backend.app.core.database import async_session_factory
from backend.app.core.redis import redis_client
from backend.app.modules.ml_engine.train_all import train_models

logger = logging.getLogger("returnshield.ml_training_worker")


async def run_worker():
    await redis_client.initialize()
    await redis_client.stream_create_group("ml:train:stream", "ml-training-workers")
    logger.info("ML training worker started")
    while True:
        messages = await redis_client.stream_read("ml:train:stream", "ml-training-workers", "worker-1", count=1, block=5000)
        if not messages:
            await asyncio.sleep(1)
            continue
        for _, entries in messages:
            for message_id, payload in entries:
                try:
                    model_types = json.loads(payload.get("model_types", "null")) if payload.get("model_types") else None
                    merchant_id = payload.get("merchant_id")
                    limit = int(payload["limit"]) if payload.get("limit") else None
                    promote_best = payload.get("promote_best", "true") != "false"
                    async with async_session_factory() as session:
                        await train_models(session, model_types=model_types, merchant_id=merchant_id, limit=limit, promote_best=promote_best, redis=redis_client)
                    await redis_client.publish("ml:training:progress", {"stage": "completed", "message_id": message_id})
                    await redis_client.stream_ack("ml:train:stream", "ml-training-workers", message_id)
                except Exception as exc:
                    logger.exception("Training job failed: %s", exc)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
