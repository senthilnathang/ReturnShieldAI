from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.prod_models.customer import Customer
from backend.app.prod_models.customer_identity import CustomerIdentity
from app.repositories.base import BaseRepository


class CustomerRepository(BaseRepository[Customer]):
    def __init__(self, session: AsyncSession):
        super().__init__(Customer, session)

    async def find_by_email_hash(self, merchant_id: UUID, email_hash: str) -> Optional[Customer]:
        query = select(Customer).where(
            Customer.merchant_id == merchant_id,
            Customer.email_hash == email_hash,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def find_by_external_id(self, merchant_id: UUID, external_id: str) -> Optional[Customer]:
        query = select(Customer).where(
            Customer.merchant_id == merchant_id,
            Customer.external_customer_id == external_id,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def find_or_create(
        self,
        merchant_id: UUID,
        external_customer_id: Optional[str] = None,
        email_hash: Optional[str] = None,
        **kwargs,
    ) -> Customer:
        if external_customer_id:
            existing = await self.find_by_external_id(merchant_id, external_customer_id)
            if existing:
                return existing

        if email_hash:
            existing = await self.find_by_email_hash(merchant_id, email_hash)
            if existing:
                return existing

        return await self.create(
            merchant_id=merchant_id,
            external_customer_id=external_customer_id,
            email_hash=email_hash,
            **kwargs,
        )


class CustomerIdentityRepository(BaseRepository[CustomerIdentity]):
    def __init__(self, session: AsyncSession):
        super().__init__(CustomerIdentity, session)

    async def find_linked_customers(
        self, merchant_id: UUID, identity_type: str, identity_value_hash: str
    ) -> list[CustomerIdentity]:
        query = select(CustomerIdentity).where(
            CustomerIdentity.merchant_id == merchant_id,
            CustomerIdentity.identity_type == identity_type,
            CustomerIdentity.identity_value_hash == identity_value_hash,
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_or_create(
        self,
        customer_id: UUID,
        merchant_id: UUID,
        identity_type: str,
        identity_value_hash: str,
    ) -> CustomerIdentity:
        query = select(CustomerIdentity).where(
            CustomerIdentity.customer_id == customer_id,
            CustomerIdentity.merchant_id == merchant_id,
            CustomerIdentity.identity_type == identity_type,
            CustomerIdentity.identity_value_hash == identity_value_hash,
        )
        result = await self.session.execute(query)
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        return await self.create(
            customer_id=customer_id,
            merchant_id=merchant_id,
            identity_type=identity_type,
            identity_value_hash=identity_value_hash,
        )
