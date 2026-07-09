from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OrderCreate(BaseModel):
    merchant_id: UUID
    customer_id: UUID
    external_order_id: Optional[str] = None
    sku: Optional[str] = None
    product_name: Optional[str] = None
    category: Optional[str] = None
    product_value: Optional[float] = None
    quantity: int = 1
    payment_method: Optional[str] = None
    payment_method_risk_score: int = 0
    order_status: Optional[str] = None
    order_date: Optional[datetime] = None
    delivery_date: Optional[datetime] = None


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    merchant_id: UUID
    customer_id: UUID
    external_order_id: Optional[str] = None
    sku: Optional[str] = None
    product_name: Optional[str] = None
    category: Optional[str] = None
    product_value: Optional[float] = None
    quantity: int
    payment_method: Optional[str] = None
    payment_method_risk_score: int
    order_status: Optional[str] = None
    order_date: Optional[datetime] = None
    delivery_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
