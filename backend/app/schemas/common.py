from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Any
from uuid import UUID



class CustomerPayload(BaseModel):
    name: str
    email: str
    phone: str = ""
    account_age_days: int = 0
    address: str = ""
    device_id: str = ""
    lifetime_orders: int = 0
    lifetime_returns: int = 0


class OrderPayload(BaseModel):
    sku: str
    product_name: str
    category: str
    product_value: float
    expected_weight: float
    payment_method: str = "card"
    payment_method_risk_score: int = 0
    delivery_date: datetime
    delivery_status: str = "delivered"


class ReturnPayload(BaseModel):
    return_reason: str
    chat_transcript: str = ""
    email_text: str = ""
    returned_weight: float = 0.0
    condition_reported: str = "unknown"
    delivery_photo_url: str = ""
    return_photo_url: str = ""
    shipping_label_text: str = ""
    ocr_text: str = ""


class ScoreRequest(BaseModel):
    customer: CustomerPayload
    order: OrderPayload
    return_data: ReturnPayload

    model_config = ConfigDict(populate_by_name=True)


class ScoreBreakdown(BaseModel):
    rule_score: float
    structured_ml_score: float
    nlp_score: float
    anomaly_score: float


class ExplainabilitySignal(BaseModel):
    label: str
    score: float
    weight: float
    impact: float
    tone: str
    detail: str


class ExplainabilityDriver(BaseModel):
    label: str
    impact: float
    detail: str


class ExplainabilityPanel(BaseModel):
    signal_contributions: list[ExplainabilitySignal]
    top_positive_drivers: list[ExplainabilityDriver]
    top_negative_drivers: list[ExplainabilityDriver]
    why_flagged_summary: str


class ReturnScoreResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    return_id: UUID
    case_id: UUID
    customer_risk_score: float
    risk_score: float
    risk_level: str
    decision: str
    recommended_action: str
    score_breakdown: ScoreBreakdown
    reason_codes: list[str]
    explanation: str
    decision_trace: list[dict[str, str | float]]
    explainability: ExplainabilityPanel
    advanced_signals: dict[str, Any]
    model_version: str | None = None


class AnalystDecisionPayload(BaseModel):
    decision: str
    status: str | None = None
    assigned_to: str | None = None
    notes: str = ""
    confirmed_label: str | None = None


class RuleCreate(BaseModel):
    name: str
    description: str = ""
    condition: str
    score: int
    enabled: bool = True


class RuleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    condition: str | None = None
    score: int | None = None
    enabled: bool | None = None


class RuleRead(RuleCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime


class CaseSummary(BaseModel):
    id: UUID
    return_id: UUID
    customer_name: str
    product_name: str
    return_reason: str
    customer_risk_score: float = 0.0
    risk_score: float
    risk_level: str
    decision: str
    status: str
    created_at: datetime


class CaseDetail(CaseSummary):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)
    customer: CustomerPayload
    order: OrderPayload
    return_data: ReturnPayload
    score_breakdown: ScoreBreakdown
    reason_codes: list[str]
    explanation: str
    recommended_action: str
    decision_trace: list[dict[str, str | float]]
    explainability: ExplainabilityPanel
    advanced_signals: dict[str, Any]
    timeline: list[dict[str, str]]


class MetricsResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    totals: dict[str, float | int]
    charts: dict[str, list[dict[str, float | int | str]]]
    model: dict[str, float | int | str | None]


class FeedbackRead(BaseModel):
    id: UUID
    case_id: UUID
    analyst_decision: str
    confirmed_label: str
    notes: str
    created_at: datetime
    customer_name: str
    product_name: str
    risk_score: float
    risk_level: str
