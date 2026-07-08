from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class AnalystFeedbackBase(SQLModel):
    case_id: UUID = Field(foreign_key="returncase.id", index=True)
    analyst_decision: str
    confirmed_label: str
    notes: str = ""


class AnalystFeedback(AnalystFeedbackBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
