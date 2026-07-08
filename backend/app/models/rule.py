from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class RuleBase(SQLModel):
    name: str
    description: str = ""
    condition: str
    score: int = 0
    enabled: bool = True


class Rule(RuleBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)
