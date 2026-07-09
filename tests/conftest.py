from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import AsyncGenerator, Generator
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from backend.app.db.base import Base
from backend.app.core.config import settings
from backend.app.prod_models.model_training_run import ModelTrainingRun  # noqa: F401

# Use test database
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql://returnshield:returnshield_secret@localhost:5432/returnshield_test")
TEST_DATABASE_URL_ASYNC = os.getenv("TEST_DATABASE_URL_ASYNC", "postgresql+asyncpg://returnshield:returnshield_secret@localhost:5432/returnshield_test")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(TEST_DATABASE_URL_ASYNC, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def sample_merchant_id(db_session: AsyncSession) -> UUID:
    from backend.app.prod_models.merchant import Merchant
    from sqlalchemy import select

    merchant = Merchant(name="Test Merchant", industry="e-commerce")
    db_session.add(merchant)
    await db_session.flush()
    return merchant.id


@pytest_asyncio.fixture
async def sample_customer_id(db_session: AsyncSession, sample_merchant_id: UUID) -> UUID:
    from backend.app.prod_models.customer import Customer

    customer = Customer(merchant_id=sample_merchant_id, name="Test Customer", email_hash="test_hash")
    db_session.add(customer)
    await db_session.flush()
    return customer.id
