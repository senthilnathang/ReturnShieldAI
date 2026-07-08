from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class OrderBase(SQLModel):
    customer_id: UUID = Field(foreign_key="customer.id", index=True)
    sku: str
    product_name: str
    category: str
    product_value: float
    expected_weight: float
    payment_method: str
    payment_method_risk_score: int = 0
    delivery_date: datetime
    delivery_status: str


class Order(OrderBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
