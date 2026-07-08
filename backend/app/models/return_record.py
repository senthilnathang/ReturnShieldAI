from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class ReturnRecordBase(SQLModel):
    order_id: UUID = Field(foreign_key="order.id", index=True)
    customer_id: UUID = Field(foreign_key="customer.id", index=True)
    return_reason: str
    chat_transcript: str = ""
    email_text: str = ""
    returned_weight: float = 0.0
    condition_reported: str = "unknown"


class ReturnRecord(ReturnRecordBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    return_date: datetime = Field(default_factory=datetime.utcnow, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
