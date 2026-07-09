from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FraudScoreCreate(BaseModel):
    merchant_id: UUID
    return_id: UUID
    customer_id: UUID
    rule_score: int = 0
    structured_ml_score: int = 0
    nlp_score: int = 0
    graph_score: int = 0
    anomaly_score: int = 0
    final_score: int = 0
    risk_level: Optional[str] = None
    decision: Optional[str] = None
    reason_codes_json: Optional[list[str]] = None
    score_breakdown_json: Optional[dict[str, Any]] = None


class FraudScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    merchant_id: UUID
    return_id: UUID
    customer_id: UUID
    rule_score: int
    structured_ml_score: int
    nlp_score: int
    graph_score: int
    anomaly_score: int
    final_score: int
    risk_level: Optional[str] = None
    decision: Optional[str] = None
    reason_codes_json: Optional[Any] = None
    score_breakdown_json: Optional[dict[str, Any]] = None
    created_at: datetime


class FraudCaseCreate(BaseModel):
    merchant_id: UUID
    return_id: UUID
    customer_id: UUID
    fraud_score_id: Optional[UUID] = None
    case_status: str = "OPEN"
    priority: Optional[str] = None
    assigned_to: Optional[str] = None
    recommended_action: Optional[str] = None
    case_summary: Optional[str] = None


class FraudCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    merchant_id: UUID
    return_id: UUID
    customer_id: UUID
    fraud_score_id: Optional[UUID] = None
    case_status: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[str] = None
    recommended_action: Optional[str] = None
    case_summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None


class FraudCaseStatusUpdate(BaseModel):
    case_status: str
    assigned_to: Optional[str] = None
