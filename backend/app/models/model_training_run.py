from datetime import datetime
from uuid import UUID, uuid4
from pydantic import ConfigDict

from sqlmodel import Field, SQLModel


class ModelTrainingRun(SQLModel, table=True):
    model_config = ConfigDict(protected_namespaces=())
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    model_version: str
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    labels_collected: int = 0
    started_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    completed_at: datetime = Field(default_factory=datetime.utcnow, index=True)
