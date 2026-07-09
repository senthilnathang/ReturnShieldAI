from __future__ import annotations

"""
Realtime Scoring Worker — consumes Redis Stream and runs scoring stub.

Usage:
    python -m app.workers.realtime_worker --consumer worker-1
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
from uuid import UUID

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import async_session_factory
from app.core.logging import setup_logging
from app.core.redis import RedisClient, redis_client
from app.services.realtime_service import RealtimeService
from app.services.scoring_stub_service import ScoringStubService

logger = logging.getLogger("returnshield.worker.realtime")
SHUTDOWN = False


def handle_signal(signum, frame):
    global SHUTDOWN
    SHUTDOWN = True
    logger.info("Shutdown signal received, draining...")


async def run_worker(consumer: str):
    global SHUTDOWN
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    await redis_client.initialize()
    realtime = RealtimeService(redis_client)
    await realtime.ensure_scoring_group()

    logger.info("Worker '%s' started, waiting for scoring events...", consumer)

    while not SHUTDOWN:
        try:
            events = await realtime.consume_scoring_events(consumer, count=10, block=5000)

            for event in events:
                data = event["data"]
                return_id = UUID(data["return_id"])
                logger.info("Processing return %s", return_id)

                async with async_session_factory() as session:
                    scoring = ScoringStubService(session)
                    result = await scoring.score_return(return_id)
                    score_record, fraud_case = await scoring.save_score_and_case(return_id, result)

                    # Publish events
                    await realtime.publish_score_updated(
                        return_id, result.final_score, score_record.merchant_id
                    )
                    if fraud_case:
                        await realtime.publish_fraud_case(
                            fraud_case.id, fraud_case.merchant_id, result.risk_level
                        )
                    await realtime.request_dashboard_refresh(score_record.merchant_id)

                await realtime.acknowledge_event(RealtimeService.SCORING_STREAM, event["id"])
                logger.info("Completed return %s (score=%d)", return_id, result.final_score)

        except Exception as e:
            logger.error("Worker error: %s", str(e), exc_info=True)
            await asyncio.sleep(1)

    logger.info("Worker '%s' stopped", consumer)


def main():
    setup_logging()
    parser = argparse.ArgumentParser(description="Realtime Scoring Worker")
    parser.add_argument("--consumer", default="worker-1", help="Consumer name")
    args = parser.parse_args()

    asyncio.run(run_worker(args.consumer))


if __name__ == "__main__":
    main()
