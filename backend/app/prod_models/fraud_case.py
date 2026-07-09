from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FraudCase(Base):
    __tablename__ = "fraud_cases"

    merchant_id: Mapped[UUID] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    return_id: Mapped[UUID] = mapped_column(ForeignKey("return_requests.id"), nullable=False)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    fraud_score_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("fraud_scores.id"))
    case_status: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    priority: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    assigned_to: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    recommended_action: Mapped[Optional[str]] = mapped_column(Text)
    case_summary: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    merchant = relationship("Merchant", backref="fraud_cases")
    return_request = relationship("ReturnRequest", backref="fraud_cases")
    customer = relationship("Customer", backref="fraud_cases")
    fraud_score = relationship("FraudScore", backref="fraud_cases")
