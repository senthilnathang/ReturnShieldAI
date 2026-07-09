from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CustomerCreate(BaseModel):
    merchant_id: UUID
    external_customer_id: Optional[str] = None
    name: Optional[str] = None
    email_hash: Optional[str] = None
    phone_hash: Optional[str] = None
    account_age_days: int = 0
    lifetime_orders: int = 0
    lifetime_returns: int = 0
    lifetime_refunds: Optional[float] = 0


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    email_hash: Optional[str] = None
    phone_hash: Optional[str] = None
    account_age_days: Optional[int] = None
    lifetime_orders: Optional[int] = None
    lifetime_returns: Optional[int] = None
    lifetime_refunds: Optional[float] = None
    customer_risk_score: Optional[int] = None


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    merchant_id: UUID
    external_customer_id: Optional[str] = None
    name: Optional[str] = None
    email_hash: Optional[str] = None
    phone_hash: Optional[str] = None
    account_age_days: int = 0
    lifetime_orders: int = 0
    lifetime_returns: int = 0
    lifetime_refunds: Optional[float] = 0
    customer_risk_score: int = 0
    created_at: datetime
    updated_at: datetime


class CustomerIdentityCreate(BaseModel):
    customer_id: UUID
    merchant_id: UUID
    identity_type: str = Field(..., description="email, phone, address, device, ip, payment_card, upi_id, refund_account, browser_fingerprint")
    identity_value_hash: str


class CustomerIdentityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    merchant_id: UUID
    identity_type: str
    identity_value_hash: str
    first_seen_at: datetime
    last_seen_at: datetime
