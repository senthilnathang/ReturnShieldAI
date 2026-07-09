from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class DashboardOverview(BaseModel):
    total_returns: int = 0
    high_risk_cases: int = 0
    manual_review_cases: int = 0
    auto_approved_cases: int = 0
    average_risk_score: float = 0.0
    fraud_prevented_estimate: float = 0.0


class RiskDistributionItem(BaseModel):
    range: str
    count: int
    percentage: float


class RecentCase(BaseModel):
    case_id: UUID
    return_id: UUID
    customer_name: Optional[str] = None
    product_name: Optional[str] = None
    risk_score: int
    risk_level: str
    decision: str
    case_status: str
    created_at: datetime


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int
    total_pages: int


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    postgres: str = "unknown"
    redis: str = "unknown"


class ImportJobCreate(BaseModel):
    source_name: str
    file_name: str
    metadata_json: Optional[dict[str, Any]] = None


class ImportJobRead(BaseModel):
    id: UUID
    source_name: Optional[str] = None
    file_name: Optional[str] = None
    status: Optional[str] = None
    total_rows: int = 0
    processed_rows: int = 0
    failed_rows: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata_json: Optional[dict[str, Any]] = None
    created_at: datetime
