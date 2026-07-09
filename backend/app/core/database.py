from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

async_engine = create_async_engine(
    settings.database_url,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.debug,
)

sync_engine = create_engine(
    settings.database_url_sync,
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.debug,
)

async_session_factory = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

sync_session_factory = sessionmaker(
    sync_engine,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_sync_session():
    session = sync_session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
