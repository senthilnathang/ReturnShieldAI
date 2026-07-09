from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReturnItem(Base):
    __tablename__ = "return_items"

    return_id: Mapped[UUID] = mapped_column(ForeignKey("return_requests.id"), nullable=False, index=True)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    sku: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    product_name: Mapped[Optional[str]] = mapped_column(String(500))
    category: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    declared_condition: Mapped[Optional[str]] = mapped_column(String(100))
    warehouse_condition: Mapped[Optional[str]] = mapped_column(String(100))
    serial_number_hash: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    imei_hash: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    item_match_status: Mapped[Optional[str]] = mapped_column(String(50), index=True)

    return_request = relationship("ReturnRequest", backref="items")
    order = relationship("Order", backref="return_items")
