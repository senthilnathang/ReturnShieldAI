from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TopFeature(BaseModel):
    feature: str
    value: Any = None
    impact: str = "medium"


class PredictionRequest(BaseModel):
    return_id: UUID
    model_type: Optional[str] = None
    model_version: Optional[str] = None


class PredictionBatchRequest(BaseModel):
    return_ids: list[UUID]
    model_type: Optional[str] = None
    model_version: Optional[str] = None


class PredictionResponse(BaseModel):
    return_id: str
    model_type: str
    model_version: str
    fraud_probability: float
    ml_score: int
    risk_level: str
    top_features: list[TopFeature] = Field(default_factory=list)
    latency_ms: int
    cached: bool = False
    fallback_used: bool = False


class TrainingRequest(BaseModel):
    model_types: list[str] | None = None
    merchant_id: Optional[UUID] = None
    limit: Optional[int] = None
    promote_best: bool = True
    enqueue_only: bool = False


class TrainingMetric(BaseModel):
    model_name: str
    version: str
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    pr_auc: float
    false_positive_rate: float
    false_negative_rate: float
    training_time_seconds: float
    prediction_latency_ms: float
    artifact_path: str
    created_at: datetime | None = None


class TrainingComparisonResponse(BaseModel):
    results: list[TrainingMetric]
    best_model_type: Optional[str] = None
    best_version: Optional[str] = None
    best_artifact_path: Optional[str] = None


class ModelSummary(BaseModel):
    model_name: str
    model_type: str
    version: str
    is_best: bool = False
    artifact_path: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


class BestModelResponse(ModelSummary):
    model_config = ConfigDict(from_attributes=True)


class TrainingRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    model_name: str
    model_type: str
    version: str
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    pr_auc: float
    false_positive_rate: float
    false_negative_rate: float
    training_time_seconds: float
    prediction_latency_ms: float
    artifact_path: str
    metrics_json: dict[str, Any]
    metadata_json: dict[str, Any]
    is_best: bool
    promoted_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
