"""
Load CSV data into a specific model/table with schema verification.

Usage:
  python script.py --file data.csv --model customers
  python script.py --file data.csv --model return_requests --verify-schema
  python script.py --file data.csv --model orders --truncate --batch-size 10000

Features:
  - Auto-detects table columns from DB schema
  --verify-schema: prints column mapping + mismatches before loading
  - Bulk INSERT via execute_values (fast)
  - Handles UUID primary keys automatically
  - Ignores unknown CSV columns by default
"""

import argparse
import logging
import os
import sys
import time
from uuid import UUID

import pandas as pd
from psycopg2 import connect
from psycopg2.extras import execute_values, register_uuid

register_uuid()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("csv_loader")


def get_table_columns(cur, table: str) -> list[dict]:
    """Fetch column names, types, nullable from information_schema."""
    cur.execute("""
        SELECT column_name, data_type, is_nullable, ordinal_position
        FROM information_schema.columns
        WHERE table_name = %s AND table_schema = 'public'
        ORDER BY ordinal_position
    """, (table,))
    cols = []
    for row in cur.fetchall():
        cols.append({
            "name": row[0],
            "type": row[1],
            "nullable": row[2] == "YES",
            "position": row[3],
        })
    return cols


def verify_schema(cur, table: str, csv_columns: list[str]):
    """Compare CSV columns to table schema and report."""
    db_cols = get_table_columns(cur, table)
    db_names = {c["name"] for c in db_cols}
    csv_set = set(csv_columns)

    matched = csv_set & db_names
    unknown = csv_set - db_names
    missing = db_names - csv_set

    logger.info("Table: %s (%d columns)", table, len(db_cols))
    logger.info("CSV columns: %d", len(csv_columns))
    logger.info("Matched: %d columns", len(matched))
    if unknown:
        logger.warning("Unknown CSV columns (will be ignored): %s", ", ".join(sorted(unknown)))
    if missing:
        missing_required = [c for c in db_cols if c["name"] in missing and not c["nullable"]]
        if missing_required:
            logger.error("REQUIRED columns missing from CSV: %s",
                        ", ".join(c["name"] for c in missing_required))
            return False
        logger.info("Optional DB columns missing (will use defaults): %s",
                    ", ".join(sorted(missing)))
    return True


def load_table(file_path: str, table: str, cur, batch_size: int = 10000):
    """Stream CSV and bulk insert into table."""
    db_cols = get_table_columns(cur, table)
    db_col_names = [c["name"] for c in db_cols]
    db_col_set = set(db_col_names)

    total = 0
    t_start = time.time()
    chunk_idx = 0

    for chunk in pd.read_csv(file_path, chunksize=batch_size, dtype=str, keep_default_na=False):
        chunk = chunk.replace({float("nan"): None, "": None})
        chunk_idx += 1
        n = len(chunk)
        total += n

        # Filter to only known columns, in DB column order
        csv_cols = [c for c in db_col_names if c in chunk.columns]
        rows = [tuple(None if pd.isna(row[c]) else row[c] for c in csv_cols)
                for _, row in chunk.iterrows()]

        col_list = ", ".join(csv_cols)
        placeholders = "%s"
        sql = f"INSERT INTO {table} ({col_list}) VALUES {placeholders}"

        t0 = time.time()
        execute_values(cur, sql, rows, page_size=5000)
        t1 = time.time()

        if chunk_idx % 5 == 0:
            elapsed = time.time() - t_start
            rate = total / elapsed if elapsed > 0 else 0
            logger.info("  Chunk %d: %s rows in %.1fs (%.0f rows/s, total: %s)",
                        chunk_idx, f"{n:,}", t1 - t0, rate, f"{total:,}")

    elapsed = time.time() - t_start
    rate = total / elapsed if elapsed > 0 else 0
    logger.info("=" * 60)
    logger.info("DONE: %s rows into '%s' in %.1fs (%.0f rows/s)",
                f"{total:,}", table, elapsed, rate)


def main():
    parser = argparse.ArgumentParser(
        description="Load CSV into a DB table with schema verification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--file", required=True, help="Path to CSV file")
    parser.add_argument("--model", required=True, help="Target table name (e.g. customers, orders)")
    parser.add_argument("--verify-schema", action="store_true", help="Check CSV vs DB columns then exit")
    parser.add_argument("--batch-size", type=int, default=10000, help="Rows per batch (default 10k)")
    parser.add_argument("--truncate", action="store_true", help="TRUNCATE table before loading")
    parser.add_argument("--env-file", default=None, help="Path to .env file with DATABASE_URL_SYNC")
    parser.add_argument("--dry-run", action="store_true", help="Verify + print column mapping only")

    args = parser.parse_args()

    if args.env_file:
        with open(args.env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

    db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL", "")
    db_url = db_url.replace("+asyncpg", "").replace("+psycopg2", "")
    if not db_url:
        logger.error("DATABASE_URL_SYNC not set.")
        sys.exit(1)

    conn = connect(db_url)
    cur = conn.cursor()

    # Read CSV header
    df_header = pd.read_csv(args.file, nrows=0)
    csv_cols = list(df_header.columns)

    # Verify schema
    ok = verify_schema(cur, args.model, csv_cols)
    if not ok:
        conn.close()
        sys.exit(1)

    if args.verify_schema or args.dry_run:
        conn.close()
        logger.info("Schema verified. No data loaded.")
        return

    if args.truncate:
        cur.execute(f"TRUNCATE TABLE {args.model} CASCADE")
        conn.commit()
        logger.info("Truncated table: %s", args.model)

    load_table(args.file, args.model, cur, args.batch_size)
    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
