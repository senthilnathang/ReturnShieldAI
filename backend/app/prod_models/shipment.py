from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class Shipment(Base):
    __tablename__ = "shipments"

    merchant_id: Mapped[UUID] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    carrier: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    tracking_number_hash: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    delivery_status: Mapped[Optional[str]] = mapped_column(String(50))
    delivery_address_hash: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    pickup_address_hash: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    expected_weight: Mapped[Optional[float]] = mapped_column(Numeric(10, 3))
    scanned_delivery_weight: Mapped[Optional[float]] = mapped_column(Numeric(10, 3))
    returned_weight: Mapped[Optional[float]] = mapped_column(Numeric(10, 3))
    weight_difference: Mapped[Optional[float]] = mapped_column(Numeric(10, 3), index=True)
    delivery_confirmation_type: Mapped[Optional[str]] = mapped_column(String(50))
    delivery_photo_url: Mapped[Optional[str]] = mapped_column(Text)
    warehouse_scan_status: Mapped[Optional[str]] = mapped_column(String(50))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    merchant = relationship("Merchant", backref="shipments")
    order = relationship("Order", backref="shipments")
