#!/usr/bin/env python3
"""
Import a Kaggle CSV dataset into ReturnShieldAI.

Usage:
    python -m backend.app.scripts.import_kaggle_dataset \\
        --file data/kaggle_returns.csv \\
        --merchant <merchant-id> \\
        --source kaggle

If --merchant is not provided, a demo merchant will be created.
"""

import argparse
import asyncio
import logging
import os
import sys
from uuid import UUID

# Ensure PYTHONPATH is set
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from ..core.database import async_session_factory, sync_session_factory
from ..core.logging import setup_logging
from backend.app.prod_models.merchant import Merchant
from ..services.import_service import ImportService

logger = logging.getLogger("returnshield.scripts.import_kaggle")


async def ensure_merchant(merchant_id: str | None) -> UUID:
    """Get or create a demo merchant."""
    if merchant_id:
        return UUID(merchant_id)

    # Create demo merchant via sync session
    from sqlalchemy import select

    with sync_session_factory() as session:
        existing = session.execute(select(Merchant).where(Merchant.name == "Demo Merchant")).scalar_one_or_none()
        if existing:
            return existing.id

        merchant = Merchant(name="Demo Merchant", industry="e-commerce")
        session.add(merchant)
        session.flush()
        logger.info("Created demo merchant: %s", merchant.id)
        return merchant.id


async def run(file_path: str, merchant_id: str | None, source: str, chunk_size: int):
    mid = await ensure_merchant(merchant_id)
    logger.info("Using merchant: %s", mid)
    logger.info("Importing: %s (chunk_size=%d)", file_path, chunk_size)

    if not os.path.exists(file_path):
        logger.error("File not found: %s", file_path)
        sys.exit(1)

    async with async_session_factory() as session:
        service = ImportService(session)
        job = await service.import_csv(file_path, mid, source, chunk_size)

    logger.info("=" * 60)
    logger.info("Import complete!")
    logger.info("  Job ID:     %s", job.id)
    logger.info("  Status:     %s", job.status)
    logger.info("  Total rows: %d", job.total_rows)
    logger.info("  Processed:  %d", job.processed_rows)
    logger.info("  Failed:     %d", job.failed_rows)
    if job.error_message:
        logger.info("  Error:      %s", job.error_message)
    logger.info("=" * 60)


def main():
    setup_logging()
    parser = argparse.ArgumentParser(description="Import Kaggle CSV into ReturnShieldAI")
    parser.add_argument("--file", required=True, help="Path to CSV file")
    parser.add_argument("--merchant", help="Merchant UUID (creates demo if omitted)")
    parser.add_argument("--source", default="kaggle", help="Source name for import job")
    parser.add_argument("--chunk-size", type=int, default=10_000, help="Rows per chunk")
    args = parser.parse_args()

    asyncio.run(run(args.file, args.merchant, args.source, args.chunk_size))


if __name__ == "__main__":
    main()
