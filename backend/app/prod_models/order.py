from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Order(Base):
    __tablename__ = "orders"

    merchant_id: Mapped[UUID] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    external_order_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    sku: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    product_name: Mapped[Optional[str]] = mapped_column(String(500))
    category: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    product_value: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    payment_method: Mapped[Optional[str]] = mapped_column(String(50))
    payment_method_risk_score: Mapped[int] = mapped_column(Integer, default=0)
    order_status: Mapped[Optional[str]] = mapped_column(String(50))
    order_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    delivery_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
