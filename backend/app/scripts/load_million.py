#!/usr/bin/env python3
"""
Load 1M+ records from a Kaggle CSV into PostgreSQL.

Sources .env file for DATABASE_URL. Supports two modes:
  1. Local CSV:  --file data/returns.csv
  2. Kaggle:     --kaggle bpraju1996/ecommerce-return-history --file data/returns.csv

Usage:
    python -m app.scripts.load_million --file /path/to/large.csv \\
        --env-file /opt/ReturnShieldAI/.env.local \\
        --merchant <uuid> --chunk-size 25000

    python -m app.scripts.load_million --kaggle bpraju1996/ecommerce-return-history \\
        --file data/ecommerce_returns.csv --env-file .env.local
"""

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from uuid import UUID

logger = logging.getLogger("returnshield.load_million")


def load_dotenv(path: str) -> None:
    """Load a .env file into os.environ."""
    path = os.path.abspath(path)
    if not os.path.exists(path):
        logger.warning("env file not found: %s", path)
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip("\"'")
            if key and key not in os.environ:
                os.environ[key] = val
    logger.info("Loaded env file: %s", path)


async def download_kaggle(kaggle_slug: str, output_path: str) -> str:
    """Download a Kaggle dataset using the Kaggle API."""
    import subprocess

    output_dir = os.path.dirname(output_path) or "."
    os.makedirs(output_dir, exist_ok=True)
    logger.info("Downloading Kaggle dataset: %s -> %s", kaggle_slug, output_path)

    result = subprocess.run(
        ["kaggle", "datasets", "download", kaggle_slug, "--unzip", "--path", output_dir],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        logger.error("Kaggle download failed: %s", result.stderr)
        raise RuntimeError(f"Kaggle download failed: {result.stderr}")

    # Find the downloaded CSV
    for f in sorted(Path(output_dir).iterdir()):
        if f.suffix.lower() == ".csv":
            logger.info("Downloaded: %s", f)
            return str(f)
    raise FileNotFoundError(f"No CSV found after downloading {kaggle_slug}")


def guess_file_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def format_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


async def run(
    file_path: str,
    merchant_id: str | None,
    source: str,
    chunk_size: int,
    flush_interval: int = 1000,
    bulk: bool = True,
    progress_interval: int = 5000,
):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from backend.app.prod_models.merchant import Merchant
    from backend.app.services.import_service import ImportService

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set. Provide --env-file or set DATABASE_URL env var.")
        sys.exit(1)

    # Display connection info (safe)
    safe_url = db_url.replace(db_url.split("@")[0].split("://")[1], "***:***") if "@" in db_url else db_url
    logger.info("Connecting: %s", safe_url)
    logger.info("File:        %s (%s)", file_path, format_bytes(guess_file_size(file_path)))
    logger.info("Chunk size:  %s rows", f"{chunk_size:,}")
    logger.info("Mode:        %s", "bulk" if bulk else "row-by-row")

    engine = create_async_engine(db_url, pool_size=5, max_overflow=10)
    factory = async_sessionmaker(engine, class_=AsyncSession)

    async with factory() as session:
        if merchant_id:
            mid = UUID(merchant_id)
            exists = await session.execute(select(Merchant).where(Merchant.id == mid))
            if not exists.scalar_one_or_none():
                logger.error("Merchant not found: %s", mid)
                sys.exit(1)
        else:
            exists = await session.execute(select(Merchant).limit(1))
            merchant = exists.scalar_one_or_none()
            if merchant:
                mid = merchant.id
                logger.info("Using existing merchant: %s", mid)
            else:
                merchant = Merchant(name="Demo Merchant", industry="e-commerce")
                session.add(merchant)
                await session.flush()
                mid = merchant.id
                logger.info("Created demo merchant: %s", mid)

        service = ImportService(session)
        if bulk:
            import_job = await service.bulk_import_csv(file_path, mid, source, chunk_size)
        else:
            import_job = await service.import_csv(file_path, mid, source, chunk_size, flush_interval)

        await session.commit()

    await engine.dispose()

    elapsed = time.time()
    logger.info("=" * 60)
    logger.info("IMPORT COMPLETE")
    logger.info("  Job ID:     %s", import_job.id)
    logger.info("  Status:     %s", import_job.status)
    logger.info("  Total rows: %s", f"{import_job.total_rows:,}")
    logger.info("  Processed:  %s", f"{import_job.processed_rows:,}")
    logger.info("  Failed:     %s", f"{import_job.failed_rows:,}")
    if import_job.error_message:
        logger.info("  Error:      %s", import_job.error_message[:500])
    logger.info("=" * 60)

    if import_job.failed_rows > 0:
        sys.exit(2)


def main():
    parser = argparse.ArgumentParser(
        description="Load 1M+ records from Kaggle CSV into ReturnShieldAI PostgreSQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--file", required=True, help="Path to CSV file (output path if --kaggle)")
    parser.add_argument("--kaggle", help="Kaggle dataset slug (e.g. bpraju1996/ecommerce-return-history)")
    parser.add_argument("--env-file", default=".env.local", help="Path to .env file with DATABASE_URL")
    parser.add_argument("--merchant", help="Merchant UUID (uses first existing merchant if omitted)")
    parser.add_argument("--source", default="kaggle", help="Source name for import job")
    parser.add_argument("--chunk-size", type=int, default=25_000, help="Rows per chunk (default 25k)")
    parser.add_argument("--flush-interval", type=int, default=1000, help="Flush DB every N rows (row-by-row mode only)")
    parser.add_argument("--no-bulk", action="store_true", help="Disable bulk insert (use row-by-row)")
    parser.add_argument("--progress-interval", type=int, default=5, help="Log progress every N seconds")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")

    args = parser.parse_args()

    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )

    # Load env file
    if args.env_file:
        load_dotenv(args.env_file)

    csv_path = os.path.abspath(args.file)

    async def entry():
        nonlocal csv_path
        if args.kaggle:
            csv_path = await download_kaggle(args.kaggle, os.path.dirname(csv_path))
        await run(
            file_path=csv_path,
            merchant_id=args.merchant,
            source=args.source,
            chunk_size=args.chunk_size,
            flush_interval=args.flush_interval,
            bulk=not args.no_bulk,
            progress_interval=args.progress_interval,
        )

    asyncio.run(entry())


if __name__ == "__main__":
    main()
