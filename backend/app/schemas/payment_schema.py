from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    merchant_id: UUID
    customer_id: UUID
    order_id: UUID
    payment_method: Optional[str] = None
    payment_token_hash: Optional[str] = None
    upi_hash: Optional[str] = None
    card_bin: Optional[str] = None
    amount: Optional[float] = None
    chargeback_flag: bool = False
    chargeback_date: Optional[datetime] = None
    created_at: datetime
