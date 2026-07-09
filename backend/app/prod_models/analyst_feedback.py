from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class AnalystFeedback(Base):
    __tablename__ = "analyst_feedback"

    merchant_id: Mapped[UUID] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    case_id: Mapped[UUID] = mapped_column(ForeignKey("fraud_cases.id"), nullable=False)
    return_id: Mapped[UUID] = mapped_column(ForeignKey("return_requests.id"), nullable=False)
    analyst_decision: Mapped[Optional[str]] = mapped_column(String(50))
    confirmed_label: Mapped[Optional[str]] = mapped_column(String(50))
    notes: Mapped[Optional[str]] = mapped_column(Text)
