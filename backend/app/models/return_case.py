from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class ReturnCaseBase(SQLModel):
    return_id: UUID = Field(foreign_key="returnrecord.id", index=True)
    risk_score: float = 0.0
    risk_level: str = "LOW"
    decision: str = "AUTO_APPROVE"
    status: str = "OPEN"
    recommended_action: str = ""
    assigned_to: str | None = None


class ReturnCase(ReturnCaseBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)
