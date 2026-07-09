from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReturnRequest(Base):
    __tablename__ = "return_requests"

    merchant_id: Mapped[UUID] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    shipment_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("shipments.id"), index=True)
    external_return_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    return_reason: Mapped[Optional[str]] = mapped_column(Text)
    condition_reported: Mapped[Optional[str]] = mapped_column(String(100))
    return_status: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    return_channel: Mapped[Optional[str]] = mapped_column(String(50))
    return_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    hours_after_delivery: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    merchant = relationship("Merchant", backref="return_requests")
    customer = relationship("Customer", backref="return_requests")
    order = relationship("Order", backref="return_requests")
    shipment = relationship("Shipment", backref="return_requests")
