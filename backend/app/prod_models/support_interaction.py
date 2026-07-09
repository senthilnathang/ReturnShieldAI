from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SupportInteraction(Base):
    __tablename__ = "support_interactions"

    merchant_id: Mapped[UUID] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    return_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("return_requests.id"), index=True)
    channel: Mapped[Optional[str]] = mapped_column(String(50))
    subject: Mapped[Optional[str]] = mapped_column(String(500))
    message_text: Mapped[Optional[str]] = mapped_column(Text)
    message_embedding_id: Mapped[Optional[str]] = mapped_column(String(255))
    sentiment_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 3))
    urgency_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 3))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    merchant = relationship("Merchant", backref="support_interactions")
    customer = relationship("Customer", backref="support_interactions")
    return_request = relationship("ReturnRequest", backref="support_interactions")
