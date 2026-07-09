from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class Refund(Base):
    __tablename__ = "refunds"

    merchant_id: Mapped[UUID] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    return_id: Mapped[UUID] = mapped_column(ForeignKey("return_requests.id"), nullable=False, index=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    refund_method: Mapped[Optional[str]] = mapped_column(String(50))
    refund_account_hash: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    refund_amount: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    refund_status: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    refund_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)

    merchant = relationship("Merchant", backref="refunds")
    return_request = relationship("ReturnRequest", backref="refunds")
    customer = relationship("Customer", backref="refunds")
