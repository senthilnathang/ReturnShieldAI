from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Payment(Base):
    __tablename__ = "payments"

    merchant_id: Mapped[UUID] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    payment_method: Mapped[Optional[str]] = mapped_column(String(50))
    payment_token_hash: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    upi_hash: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    card_bin: Mapped[Optional[str]] = mapped_column(String(10))
    amount: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    chargeback_flag: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    chargeback_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    merchant = relationship("Merchant", backref="payments")
    customer = relationship("Customer", backref="payments")
    order = relationship("Order", backref="payments")
