from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class FraudScoreBase(SQLModel):
    return_id: UUID = Field(foreign_key="returnrecord.id", index=True)
    rule_score: float
    structured_ml_score: float
    nlp_score: float
    anomaly_score: float
    final_score: float
    reason_codes_json: str
    explanation: str


class FraudScore(FraudScoreBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
