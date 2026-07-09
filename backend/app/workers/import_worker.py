from __future__ import annotations

"""
Import Worker — runs large CSV imports in the background.

Usage:
    python -m app.workers.import_worker --file data/large_import.csv --merchant-id <UUID>
"""

import argparse
import asyncio
import logging
import os
import sys
from uuid import UUID

# Ensure PYTHONPATH is set
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import async_session_factory
from app.core.logging import setup_logging
from app.services.import_service import ImportService

logger = logging.getLogger("returnshield.worker.import_worker")


async def run_import(file_path: str, merchant_id: UUID, source_name: str = "kaggle"):
    if not os.path.exists(file_path):
        logger.error("File not found: %s", file_path)
        return

    logger.info("Starting import: %s -> merchant %s", file_path, merchant_id)

    async with async_session_factory() as session:
        service = ImportService(session)
        job = await service.import_csv(file_path, merchant_id, source_name)
        logger.info(
            "Import completed: %s (status=%s, processed=%d, failed=%d)",
            job.id, job.status, job.processed_rows, job.failed_rows,
        )


def main():
    setup_logging()
    parser = argparse.ArgumentParser(description="Kaggle CSV Import Worker")
    parser.add_argument("--file", required=True, help="Path to CSV file")
    parser.add_argument("--merchant-id", required=True, type=UUID, help="Merchant UUID")
    parser.add_argument("--source", default="kaggle", help="Source name")
    args = parser.parse_args()

    asyncio.run(run_import(args.file, args.merchant_id, args.source))


if __name__ == "__main__":
    main()
