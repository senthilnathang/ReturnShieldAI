from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    merchant_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), index=True)
    entity_type: Mapped[Optional[str]] = mapped_column(String(100))
    entity_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True))
    event_type: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    event_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, default=dict)
