from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Merchant(Base):
    __tablename__ = "merchants"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100))
    risk_threshold_low: Mapped[int] = mapped_column(Integer, default=40)
    risk_threshold_high: Mapped[int] = mapped_column(Integer, default=70)
    settings_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
