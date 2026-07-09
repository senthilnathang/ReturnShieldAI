from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.repositories.customer_repository import CustomerRepository
from app.schemas.customer_schema import CustomerRead

logger = logging.getLogger("returnshield.api.customers")
router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("/{customer_id}", response_model=CustomerRead)
async def get_customer(
    customer_id: UUID,
    session: AsyncSession = Depends(get_async_session),
):
    repo = CustomerRepository(session)
    customer = await repo.get(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return CustomerRead(
        id=customer.id,
        merchant_id=customer.merchant_id,
        external_customer_id=customer.external_customer_id,
        name=customer.name,
        email_hash=customer.email_hash,
        phone_hash=customer.phone_hash,
        account_age_days=customer.account_age_days,
        lifetime_orders=customer.lifetime_orders,
        lifetime_returns=customer.lifetime_returns,
        lifetime_refunds=customer.lifetime_refunds,
        customer_risk_score=customer.customer_risk_score,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
    )
