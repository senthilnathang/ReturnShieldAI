from __future__ import annotations

import logging
from typing import Any, Generic, Optional, TypeVar
from uuid import UUID

from sqlalchemy import select, func, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.base import Base

ModelType = TypeVar("ModelType", bound=Base)
logger = logging.getLogger("returnshield.repository")


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def get(self, id: UUID) -> Optional[ModelType]:
        return await self.session.get(self.model, id)

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[str] = None,
        descending: bool = True,
        filters: Optional[dict[str, Any]] = None,
    ) -> tuple[list[ModelType], int]:
        query = select(self.model)

        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key) and value is not None:
                    query = query.where(getattr(self.model, key) == value)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_query)).scalar() or 0

        order_col = getattr(self.model, order_by, None) if order_by else getattr(self.model, "created_at", None)
        if order_col is not None:
            query = query.order_by(order_col.desc() if descending else order_col.asc())

        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        items = list(result.scalars().all())
        return items, total

    async def create(self, **kwargs) -> ModelType:
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        logger.debug("Created %s: %s", self.model.__name__, instance.id)
        return instance

    async def update(self, id: UUID, **kwargs) -> Optional[ModelType]:
        instance = await self.get(id)
        if not instance:
            return None
        for key, value in kwargs.items():
            if value is not None and hasattr(instance, key):
                setattr(instance, key, value)
        await self.session.flush()
        await self.session.refresh(instance)
        logger.debug("Updated %s: %s", self.model.__name__, id)
        return instance

    async def delete(self, id: UUID) -> bool:
        instance = await self.get(id)
        if not instance:
            return False
        await self.session.delete(instance)
        await self.session.flush()
        logger.debug("Deleted %s: %s", self.model.__name__, id)
        return True

    async def count(self, filters: Optional[dict[str, Any]] = None) -> int:
        query = select(func.count()).select_from(self.model)
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key) and value is not None:
                    query = query.where(getattr(self.model, key) == value)
        result = await self.session.execute(query)
        return result.scalar() or 0
