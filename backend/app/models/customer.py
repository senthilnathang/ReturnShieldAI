from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class CustomerBase(SQLModel):
    name: str
    email: str
    phone: str
    account_age_days: int
    lifetime_orders: int = 0
    lifetime_returns: int = 0
    address: str
    device_id: str


class Customer(CustomerBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class CustomerRead(CustomerBase):
    id: UUID
    created_at: datetime
