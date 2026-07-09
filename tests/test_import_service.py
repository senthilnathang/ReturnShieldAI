from __future__ import annotations

import csv
import tempfile
from uuid import uuid4

import pytest

from app.services.import_service import ImportService


@pytest.mark.asyncio
async def test_import_csv(db_session):
    """Test importing a small CSV with auto-mapping."""
    merchant_id = uuid4()

    # Create sample CSV
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        writer = csv.writer(f)
        writer.writerow(["customer_id", "order_id", "sku", "product_name", "product_value", "return_reason"])
        writer.writerow(["CUST001", "ORD001", "SKU-1001", "Widget A", "49.99", "Changed mind"])
        writer.writerow(["CUST002", "ORD002", "SKU-1002", "Widget B", "199.99", "Defective"])
        f.flush()
        file_path = f.name

    service = ImportService(db_session)
    job = await service.import_csv(file_path, merchant_id, source_name="test", chunk_size=100)

    assert job.status in ("completed", "completed_with_errors")
    assert job.total_rows == 2
    assert job.processed_rows == 2


@pytest.mark.asyncio
async def test_import_column_mapping(db_session):
    service = ImportService(db_session)
    mapping = service._auto_map_columns(["customer_id", "order_date", "product_value", "return_reason_text"])
    assert mapping.get("customer_id") == "customer_id"
    assert mapping.get("order_date") == "order_date"
    assert mapping.get("product_value") == "product_value"
    assert mapping.get("return_reason_text") == "return_reason"


@pytest.mark.asyncio
async def test_import_hash_function(db_session):
    service = ImportService(db_session)
    h1 = service._hash("test@example.com")
    h2 = service._hash("  TEST@example.COM  ")
    assert h1 == h2  # case-insensitive, trimmed
    assert service._hash("") is None
    assert service._hash(None) is None
