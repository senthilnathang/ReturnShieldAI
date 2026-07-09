from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReturnRequestCreate(BaseModel):
    merchant_id: UUID
    customer_id: UUID
    order_id: UUID
    shipment_id: Optional[UUID] = None
    external_return_id: Optional[str] = None
    return_reason: Optional[str] = None
    condition_reported: Optional[str] = None
    return_channel: Optional[str] = None
    return_date: Optional[datetime] = None


class ReturnRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    merchant_id: UUID
    customer_id: UUID
    order_id: UUID
    shipment_id: Optional[UUID] = None
    external_return_id: Optional[str] = None
    return_reason: Optional[str] = None
    condition_reported: Optional[str] = None
    return_status: Optional[str] = None
    return_channel: Optional[str] = None
    return_date: Optional[datetime] = None
    hours_after_delivery: Optional[float] = None
    created_at: datetime
    updated_at: datetime


class ReturnItemCreate(BaseModel):
    return_id: UUID
    order_id: UUID
    sku: Optional[str] = None
    product_name: Optional[str] = None
    category: Optional[str] = None
    declared_condition: Optional[str] = None
    warehouse_condition: Optional[str] = None
    serial_number_hash: Optional[str] = None
    imei_hash: Optional[str] = None


class ReturnItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    return_id: UUID
    order_id: UUID
    sku: Optional[str] = None
    product_name: Optional[str] = None
    category: Optional[str] = None
    declared_condition: Optional[str] = None
    warehouse_condition: Optional[str] = None
    serial_number_hash: Optional[str] = None
    imei_hash: Optional[str] = None
    item_match_status: Optional[str] = None
    created_at: datetime


class EnqueueScoreRequest(BaseModel):
    return_id: UUID


class ScoringResult(BaseModel):
    rule_score: int = 0
    structured_ml_score: int = 0
    nlp_score: int = 0
    graph_score: int = 0
    anomaly_score: int = 0
    final_score: int = 0
    risk_level: str = "LOW"
    decision: str = "AUTO_APPROVE"
    reason_codes: list[str] = Field(default_factory=list)
    score_breakdown: dict[str, Any] = Field(default_factory=dict)
