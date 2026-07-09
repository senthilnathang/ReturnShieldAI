from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FraudScore(Base):
    __tablename__ = "fraud_scores"

    merchant_id: Mapped[UUID] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    return_id: Mapped[UUID] = mapped_column(ForeignKey("return_requests.id"), nullable=False, index=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    rule_score: Mapped[int] = mapped_column(Integer, default=0)
    structured_ml_score: Mapped[int] = mapped_column(Integer, default=0)
    nlp_score: Mapped[int] = mapped_column(Integer, default=0)
    graph_score: Mapped[int] = mapped_column(Integer, default=0)
    anomaly_score: Mapped[int] = mapped_column(Integer, default=0)
    final_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    risk_level: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    decision: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    reason_codes_json: Mapped[Optional[list[Any]]] = mapped_column(JSONB, default=list)
    score_breakdown_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, default=dict)
