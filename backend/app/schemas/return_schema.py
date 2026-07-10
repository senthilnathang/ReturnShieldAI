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
    detailed_description: Optional[str] = None
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
    created_by: Optional[str] = None
    return_reason_category: Optional[str] = None
    return_reason: Optional[str] = None
    detailed_description: Optional[str] = None
    condition_reported: Optional[str] = None
    return_method: Optional[str] = None
    pickup_address_id: Optional[str] = None
    preferred_refund_method: Optional[str] = None
    return_status: Optional[str] = None
    fraud_screening_status: Optional[str] = None
    eligibility_override: bool = False
    eligibility_override_reason: Optional[str] = None
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
    quantity: int = 1
    product_value: Optional[float] = None
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
    quantity: int = 1
    product_value: Optional[float] = None
    declared_condition: Optional[str] = None
    warehouse_condition: Optional[str] = None
    serial_number_hash: Optional[str] = None
    imei_hash: Optional[str] = None
    item_match_status: Optional[str] = None
    created_at: datetime


class OrderReturnItemCreate(BaseModel):
    order_item_id: UUID
    quantity: int = Field(ge=1)
    serial_number: Optional[str] = None
    imei: Optional[str] = None


class ReturnAttachmentPlaceholder(BaseModel):
    id: Optional[str] = None
    file_type: Optional[str] = None
    file_url: Optional[str] = None
    image_type: Optional[str] = None
    uploaded_by: Optional[str] = None
    uploaded_at: Optional[datetime] = None
    analysis_status: Optional[str] = None


class OrderReturnCreate(BaseModel):
    return_reason_category: str
    return_reason: str
    detailed_description: str
    condition_reported: str
    return_method: str
    pickup_address_id: Optional[str] = None
    preferred_refund_method: str
    items: list[OrderReturnItemCreate]
    eligibility_override: bool = False
    eligibility_override_reason: Optional[str] = None
    attachments: list[ReturnAttachmentPlaceholder] = Field(default_factory=list)


class ReturnEligibilityRead(BaseModel):
    eligible: bool
    return_window_days: int
    return_window_expires_at: Optional[datetime] = None
    reason: Optional[str] = None
    message: Optional[str] = None
    returnable_item_count: int = 0
    can_override: bool = False


class ReturnableOrderItemRead(BaseModel):
    order_item_id: UUID
    order_id: UUID
    sku: Optional[str] = None
    product_name: Optional[str] = None
    category: Optional[str] = None
    ordered_quantity: int = 0
    previously_returned_quantity: int = 0
    available_return_quantity: int = 0
    return_quantity: int = 0
    product_value: Optional[float] = None
    serial_number: Optional[str] = None
    imei: Optional[str] = None
    requires_serial: bool = False


class OrderReturnRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_return_id: Optional[str] = None
    order_id: UUID
    merchant_id: UUID
    customer_id: UUID
    created_by: Optional[str] = None
    return_reason_category: Optional[str] = None
    return_reason: Optional[str] = None
    detailed_description: Optional[str] = None
    condition_reported: Optional[str] = None
    return_method: Optional[str] = None
    pickup_address_id: Optional[str] = None
    preferred_refund_method: Optional[str] = None
    return_status: Optional[str] = None
    fraud_screening_status: Optional[str] = None
    eligibility_override: bool = False
    eligibility_override_reason: Optional[str] = None
    return_date: Optional[datetime] = None
    hours_after_delivery: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    fraud_risk_score: Optional[float] = None
    fraud_decision: Optional[str] = None
    refund_amount: Optional[float] = None
    item_count: int = 0
    items: list[ReturnItemRead] = Field(default_factory=list)


class ReturnDetailRead(OrderReturnRead):
    order: dict[str, Any] = Field(default_factory=dict)
    customer: dict[str, Any] = Field(default_factory=dict)
    eligibility: Optional[ReturnEligibilityRead] = None
    timeline: list[dict[str, str]] = Field(default_factory=list)


class OrderImageCompareRequest(BaseModel):
    image_data_url: str
    filename: Optional[str] = None
    mime_type: Optional[str] = None


class OrderImageCompareRead(BaseModel):
    order_id: UUID
    matched: bool
    confidence: float = 0
    ocr_text: str = ""
    detected_product_name: Optional[str] = None
    detected_sku: Optional[str] = None
    detected_serial_number: Optional[str] = None
    detected_imei: Optional[str] = None
    mismatch_reasons: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    summary: str = ""
    provider_model: Optional[str] = None


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
