from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.redis import RedisClient
from backend.app.prod_models.audit_event import AuditEvent
from backend.app.prod_models.customer import Customer
from backend.app.prod_models.fraud_score import FraudScore
from backend.app.prod_models.order import Order
from backend.app.prod_models.payment import Payment
from backend.app.prod_models.refund import Refund
from backend.app.prod_models.return_item import ReturnItem
from backend.app.prod_models.return_request import ReturnRequest
from backend.app.prod_models.shipment import Shipment
from backend.app.prod_models.support_interaction import SupportInteraction
from backend.app.schemas.return_schema import (
    OrderImageCompareRead,
    OrderReturnCreate,
    OrderReturnItemCreate,
    OrderReturnRead,
    ReturnAnalysisRead,
    ReturnAttachmentPlaceholder,
    ReturnDetailRead,
    ReturnEligibilityRead,
    ReturnItemRead,
    ReturnableOrderItemRead,
    ScoringResult,
)
from backend.app.schemas.fraud_schema import FraudCaseRead, FraudScoreRead
from backend.app.ml.explainability import build_explainability_panel, build_explanation, recommended_action
from backend.app.services.realtime_service import RealtimeService
from backend.app.services.return_image_service import ReturnImageService, ReturnImageValidationError
from backend.app.services.scoring_stub_service import ScoringStubService

logger = logging.getLogger("returnshield.return_service")


@dataclass(slots=True)
class ReturnValidationError(Exception):
    code: str
    message: str
    status_code: int = 400


class ReturnService:
    def __init__(self, session: AsyncSession, redis: Optional[RedisClient] = None):
        self.session = session
        self.redis = redis

    async def _load_order(self, order_id: UUID) -> Order:
        order = await self.session.get(Order, order_id)
        if not order:
            raise ReturnValidationError("ORDER_NOT_FOUND", "Order not found", 404)
        return order

    async def _load_customer(self, customer_id: UUID) -> Customer | None:
        return await self.session.get(Customer, customer_id)

    async def _load_shipment(self, order_id: UUID) -> Shipment | None:
        result = await self.session.execute(select(Shipment).where(Shipment.order_id == order_id))
        return result.scalar_one_or_none()

    async def _returned_quantity(self, order_id: UUID) -> int:
        result = await self.session.execute(
            select(func.coalesce(func.sum(ReturnItem.quantity), 0)).where(ReturnItem.order_id == order_id)
        )
        return int(result.scalar() or 0)

    async def _refunded_amount(self, order_id: UUID) -> float:
        stmt = (
            select(func.coalesce(func.sum(Refund.refund_amount), 0))
            .select_from(Refund)
            .join(ReturnRequest, Refund.return_id == ReturnRequest.id)
            .where(ReturnRequest.order_id == order_id)
        )
        result = await self.session.execute(stmt)
        return float(result.scalar() or 0)

    async def _refunded_amount_for_return(self, return_id: UUID) -> float:
        stmt = select(func.coalesce(func.sum(Refund.refund_amount), 0)).where(Refund.return_id == return_id)
        result = await self.session.execute(stmt)
        return float(result.scalar() or 0)

    async def _fraud_score_for_return(self, return_id: UUID) -> tuple[float | None, str | None]:
        result = await self.session.execute(
            select(FraudScore).where(FraudScore.return_id == return_id).order_by(FraudScore.created_at.desc())
        )
        fraud = result.scalars().first()
        if not fraud:
            return None, None
        return float(fraud.final_score), fraud.decision

    def _hash_value(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        return hashlib.sha256(value.strip().encode("utf-8")).hexdigest()

    def _requires_serial(self, order: Order) -> bool:
        haystack = " ".join(filter(None, [order.category, order.product_name, order.sku])).lower()
        return any(token in haystack for token in ("phone", "mobile", "electronics", "tablet", "imei", "serial"))

    def _first_attachment(self, payload: OrderReturnCreate) -> ReturnAttachmentPlaceholder | None:
        for attachment in payload.attachments:
            if attachment.file_url:
                return attachment
        return None

    async def _run_post_submit_image_review(
        self,
        order: Order,
        return_req: ReturnRequest,
        attachment: ReturnAttachmentPlaceholder,
    ) -> OrderImageCompareRead | None:
        image_service = ReturnImageService(self.session)
        try:
            result = await image_service.compare_order_image(
                order.id,
                attachment.file_url or "",
                filename=attachment.id or attachment.image_type,
                mime_type=attachment.file_type,
                reference_image_data_url=order.delivery_image_url or order.product_image_url,
            )
        except (ReturnImageValidationError, Exception) as exc:
            logger.warning("Return image review failed for %s: %s", return_req.id, exc)
            self.session.add(
                AuditEvent(
                    merchant_id=order.merchant_id,
                    entity_type="return_request",
                    entity_id=return_req.id,
                    event_type="RETURN_IMAGE_REVIEW_FAILED",
                    event_json={"error": str(exc), "attachment_type": attachment.image_type},
                )
            )
            return None

        summary = result.summary or "Image review completed."
        self.session.add(
            SupportInteraction(
                merchant_id=order.merchant_id,
                customer_id=order.customer_id,
                return_id=return_req.id,
                channel="vision",
                subject="Return image OCR review",
                message_text=(f"OCR text: {result.ocr_text}\nSummary: {summary}"),
                message_embedding_id=f"vision-{return_req.id}",
                sentiment_score=-0.200 if result.matched else -0.650,
                urgency_score=0.300 if result.matched else 0.800,
            )
        )
        self.session.add(
            AuditEvent(
                merchant_id=order.merchant_id,
                entity_type="return_request",
                entity_id=return_req.id,
                event_type="RETURN_IMAGE_REVIEW_COMPLETED",
                event_json={
                    "matched": result.matched,
                    "confidence": result.confidence,
                    "provider_model": result.provider_model,
                    "summary": summary,
                    "ocr_text": result.ocr_text,
                    "mismatch_reasons": result.mismatch_reasons,
                    "evidence": result.evidence,
                },
            )
        )
        if not result.matched:
            self.session.add(
                AuditEvent(
                    merchant_id=order.merchant_id,
                    entity_type="return_request",
                    entity_id=return_req.id,
                    event_type="RETURN_IMAGE_MISMATCH_DETECTED",
                    event_json={"confidence": result.confidence, "reasons": result.mismatch_reasons},
                )
            )
        return result

    async def run_return_analysis(
        self,
        return_id: UUID,
        *,
        image_data_url: str | None = None,
        filename: str | None = None,
        mime_type: str | None = None,
        user_id: str | None = None,
        can_override: bool = False,
    ) -> ReturnAnalysisRead:
        return_req = await self.session.get(ReturnRequest, return_id)
        if not return_req:
            raise ReturnValidationError("RETURN_NOT_FOUND", "Return not found", 404)

        order = await self._load_order(return_req.order_id)
        image_review = None
        if image_data_url:
            image_review = await self._run_post_submit_image_review(
                order,
                return_req,
                ReturnAttachmentPlaceholder(
                    id=filename,
                    file_type=mime_type,
                    file_url=image_data_url,
                    image_type="MANUAL_RETURN_IMAGE",
                    uploaded_by=user_id,
                ),
            )
            await self.session.flush()

        scoring = ScoringStubService(self.session)
        result = await scoring.score_return(return_id)
        if image_review and not image_review.matched:
            result = result.model_copy(
                update={
                    "reason_codes": list(dict.fromkeys(["DELIVERY_REFERENCE_IMAGE_DIFFERS", *result.reason_codes])),
                    "final_score": max(result.final_score, settings.default_risk_threshold_high),
                    "risk_level": "HIGH",
                    "decision": "REJECT",
                    "score_breakdown": {
                        **(result.score_breakdown or {}),
                        "image_mismatch": 100,
                    },
                }
            )
        score_record, fraud_case = await scoring.save_score_and_case(return_id, result)
        customer = await self._load_customer(order.customer_id)

        if self.redis:
            try:
                realtime = RealtimeService(self.redis)
                await realtime.publish_score_updated(return_id, result.final_score, score_record.merchant_id)
                if fraud_case:
                    await realtime.publish_fraud_case(fraud_case.id, fraud_case.merchant_id, result.risk_level)
                await realtime.request_dashboard_refresh(score_record.merchant_id)
            except Exception as exc:
                logger.warning("Realtime publish failed after return analysis for %s: %s", return_id, exc)

        detail = await self.get_return_detail(return_id)
        detail.fraud_risk_score = float(score_record.final_score)
        detail.fraud_decision = result.decision

        customer_risk_score = float(getattr(customer, "customer_risk_score", 0) or 0)
        explainability = build_explainability_panel(
            score_breakdown={
                "rule_score": float(result.rule_score),
                "structured_ml_score": float(result.structured_ml_score),
                "nlp_score": float(result.nlp_score),
                "anomaly_score": float(result.anomaly_score),
            },
            customer_risk_score=customer_risk_score,
            reason_codes=result.reason_codes,
            decision=result.decision,
        )
        explanation = build_explanation(
            result.reason_codes,
            extra_context={
                "prefix": "Fraud review needed because",
                "fallback": "No material fraud indicators were detected.",
            },
        )
        if image_review and image_review.ocr_text:
            explanation = f"{explanation} OCR text observed: {image_review.ocr_text[:180]}"

        decision_trace = [
            {"stage": "rule_score", "value": result.rule_score},
            {"stage": "structured_ml_score", "value": result.structured_ml_score},
            {"stage": "nlp_score", "value": result.nlp_score},
            {"stage": "graph_score", "value": result.graph_score},
            {"stage": "anomaly_score", "value": result.anomaly_score},
            {"stage": "final_score", "value": result.final_score},
        ]

        return ReturnAnalysisRead(
            return_detail=detail,
            image_review=image_review,
            score=FraudScoreRead.model_validate(score_record),
            fraud_case=FraudCaseRead.model_validate(fraud_case) if fraud_case else None,
            score_result=result,
            explanation=explanation,
            recommended_action=recommended_action(result.decision),
            explainability=explainability,
            reason_codes=result.reason_codes,
            score_breakdown=result.score_breakdown,
            decision_trace=decision_trace,
            model_version=result.score_breakdown.get("ml_model_version") if isinstance(result.score_breakdown, dict) else None,
        )


    async def check_order_return_eligibility(self, order_id: UUID, can_override: bool = False) -> ReturnEligibilityRead:
        order = await self._load_order(order_id)
        shipment = await self._load_shipment(order_id)
        returned_qty = await self._returned_quantity(order_id)
        refunded_amount = await self._refunded_amount(order_id)

        now = datetime.now(timezone.utc)
        delivery_date = order.delivery_date or (shipment.created_at if shipment else None)
        return_window_expires_at = None
        if delivery_date:
            return_window_expires_at = delivery_date + timedelta(days=settings.return_window_days)

        returnable_quantity = max((order.quantity or 0) - returned_qty, 0)
        eligible = True
        reason = None
        message = None

        if order.order_status and order.order_status.upper() == "CANCELLED":
            eligible = False
            reason = "ORDER_CANCELLED"
            message = "Order is cancelled."
        elif not order.delivery_date:
            eligible = False
            reason = "ORDER_NOT_DELIVERED"
            message = "Return not available - order is not delivered."
        elif order.order_status and order.order_status.upper() != "DELIVERED":
            eligible = False
            reason = "ORDER_NOT_DELIVERED"
            message = "Return not available - order is not delivered."
        elif return_window_expires_at and now > return_window_expires_at and not can_override:
            eligible = False
            reason = "RETURN_WINDOW_EXPIRED"
            message = f"The return window expired on {return_window_expires_at.date().isoformat()}."
        elif returnable_quantity <= 0:
            eligible = False
            reason = "NO_RETURNABLE_ITEMS"
            message = "All order items have already been returned."
        elif order.product_value is not None and refunded_amount >= float(order.product_value) and not can_override:
            eligible = False
            reason = "ORDER_FULLY_REFUNDED"
            message = "Order has already been fully refunded."

        return ReturnEligibilityRead(
            eligible=eligible,
            return_window_days=settings.return_window_days,
            return_window_expires_at=return_window_expires_at,
            reason=reason,
            message=message,
            returnable_item_count=1 if returnable_quantity > 0 else 0,
            can_override=not eligible,
        )

    async def get_returnable_items(self, order_id: UUID) -> list[ReturnableOrderItemRead]:
        order = await self._load_order(order_id)
        returned_qty = await self._returned_quantity(order_id)
        available_qty = max((order.quantity or 0) - returned_qty, 0)
        return [
            ReturnableOrderItemRead(
                order_item_id=order.id,
                order_id=order.id,
                sku=order.sku,
                product_name=order.product_name,
                category=order.category,
                ordered_quantity=int(order.quantity or 0),
                previously_returned_quantity=returned_qty,
                available_return_quantity=available_qty,
                return_quantity=available_qty,
                product_value=float(order.product_value) if order.product_value is not None else None,
                requires_serial=self._requires_serial(order),
            )
        ]

    async def create_return_request(
        self,
        order_id: UUID,
        payload: OrderReturnCreate,
        user_id: Optional[str] = None,
        can_override: bool = False,
    ) -> ReturnDetailRead:
        order = await self._load_order(order_id)
        customer = await self._load_customer(order.customer_id)
        shipment = await self._load_shipment(order_id)
        eligibility = await self.check_order_return_eligibility(order_id, can_override=can_override)
        if not eligibility.eligible and not payload.eligibility_override:
            raise ReturnValidationError(eligibility.reason or "RETURN_INELIGIBLE", eligibility.message or "Order is not eligible for return")
        if not eligibility.eligible and payload.eligibility_override and not can_override:
            raise ReturnValidationError("RETURN_OVERRIDE_PERMISSION_REQUIRED", "You do not have permission to override return eligibility", 403)

        if not payload.items:
            raise ReturnValidationError("NO_RETURNABLE_ITEMS", "At least one item must be selected")

        available_items = await self.get_returnable_items(order_id)
        available_by_id = {str(item.order_item_id): item for item in available_items}
        selected_items: list[ReturnItemRead] = []
        total_quantity = 0
        for item in payload.items:
            available = available_by_id.get(str(item.order_item_id))
            if not available:
                raise ReturnValidationError("NO_RETURNABLE_ITEMS", "Selected item is not returnable")
            if item.quantity <= 0:
                raise ReturnValidationError("RETURN_QUANTITY_EXCEEDED", "Return quantity must be greater than zero")
            if item.quantity > available.available_return_quantity:
                raise ReturnValidationError("RETURN_QUANTITY_EXCEEDED", "Return quantity cannot exceed available quantity")
            if available.requires_serial and not (item.serial_number or item.imei):
                raise ReturnValidationError("INVALID_SERIAL_NUMBER", "Serialized products require a serial number or IMEI")
            total_quantity += item.quantity
            selected_items.append(
                ReturnItemRead(
                    id=order.id,
                    return_id=order.id,
                    order_id=order.id,
                    sku=available.sku,
                    product_name=available.product_name,
                    category=available.category,
                    quantity=item.quantity,
                    product_value=available.product_value,
                    declared_condition=payload.condition_reported,
                    warehouse_condition=None,
                    serial_number_hash=self._hash_value(item.serial_number),
                    imei_hash=self._hash_value(item.imei),
                    item_match_status="PENDING",
                    created_at=datetime.now(timezone.utc),
                )
            )

        if total_quantity <= 0:
            raise ReturnValidationError("RETURN_QUANTITY_EXCEEDED", "Return quantity must be greater than zero")

        if payload.return_reason_category.upper() in {"DAMAGED_PRODUCT", "DEFECTIVE_PRODUCT", "WRONG_PRODUCT", "EMPTY_BOX", "MISSING_ACCESSORIES"} and not payload.detailed_description.strip():
            raise ReturnValidationError("RETURN_DESCRIPTION_REQUIRED", "Detailed description is required for the selected return reason")

        if payload.return_method.upper() == "PICKUP" and not payload.pickup_address_id:
            raise ReturnValidationError("PICKUP_ADDRESS_REQUIRED", "Pickup address is required for pickup returns")

        count_stmt = select(func.count(ReturnRequest.id))
        count = (await self.session.execute(count_stmt)).scalar() or 0
        external_return_id = f"RET-{100000 + int(count) + 1}"
        now = datetime.now(timezone.utc)
        hours_after_delivery = None
        if order.delivery_date:
            hours_after_delivery = round((now - order.delivery_date).total_seconds() / 3600, 2)

        return_req = ReturnRequest(
            merchant_id=order.merchant_id,
            customer_id=order.customer_id,
            order_id=order.id,
            shipment_id=shipment.id if shipment else None,
            external_return_id=external_return_id,
            created_by=user_id,
            return_reason_category=payload.return_reason_category,
            return_reason=payload.return_reason,
            detailed_description=payload.detailed_description,
            condition_reported=payload.condition_reported,
            return_method=payload.return_method,
            pickup_address_id=payload.pickup_address_id,
            preferred_refund_method=payload.preferred_refund_method,
            return_status="REQUESTED",
            fraud_screening_status="PENDING",
            eligibility_override=payload.eligibility_override,
            eligibility_override_reason=payload.eligibility_override_reason,
            return_channel="ORDER_PORTAL",
            return_date=now,
            hours_after_delivery=hours_after_delivery,
        )
        self.session.add(return_req)
        await self.session.flush()

        persisted_items: list[ReturnItemRead] = []
        for item in payload.items:
            available = available_by_id[str(item.order_item_id)]
            db_item = ReturnItem(
                return_id=return_req.id,
                order_id=order.id,
                sku=available.sku,
                product_name=available.product_name,
                category=available.category,
                quantity=item.quantity,
                product_value=available.product_value,
                declared_condition=payload.condition_reported,
                warehouse_condition=None,
                serial_number_hash=self._hash_value(item.serial_number),
                imei_hash=self._hash_value(item.imei),
                item_match_status="PENDING",
            )
            self.session.add(db_item)
            await self.session.flush()
            persisted_items.append(
                ReturnItemRead(
                    id=db_item.id,
                    return_id=db_item.return_id,
                    order_id=db_item.order_id,
                    sku=db_item.sku,
                    product_name=db_item.product_name,
                    category=db_item.category,
                    quantity=db_item.quantity,
                    product_value=float(db_item.product_value) if db_item.product_value is not None else None,
                    declared_condition=db_item.declared_condition,
                    warehouse_condition=db_item.warehouse_condition,
                    serial_number_hash=db_item.serial_number_hash,
                    imei_hash=db_item.imei_hash,
                    item_match_status=db_item.item_match_status,
                    created_at=db_item.created_at,
                )
            )

        self.session.add(
            AuditEvent(
                merchant_id=order.merchant_id,
                entity_type="return_request",
                entity_id=return_req.id,
                event_type="RETURN_REQUEST_CREATED",
                event_json={
                    "order_id": str(order.id),
                    "customer_id": str(order.customer_id),
                    "created_by": user_id,
                    "eligibility_override": payload.eligibility_override,
                    "item_count": len(persisted_items),
                },
            )
        )
        if payload.eligibility_override:
            self.session.add(
                AuditEvent(
                    merchant_id=order.merchant_id,
                    entity_type="return_request",
                    entity_id=return_req.id,
                    event_type="RETURN_ELIGIBILITY_OVERRIDDEN",
                    event_json={"reason": payload.eligibility_override_reason},
                )
            )
        attachment = self._first_attachment(payload)
        if attachment:
            self.session.add(
                AuditEvent(
                    merchant_id=order.merchant_id,
                    entity_type="return_request",
                    entity_id=return_req.id,
                    event_type="RETURN_IMAGE_REVIEW_QUEUED",
                    event_json={"attachment_type": attachment.image_type, "file_type": attachment.file_type},
                )
            )
            await self.session.flush()
            await self._run_post_submit_image_review(order, return_req, attachment)
            await self.session.flush()

        if self.redis:
            try:
                realtime = RealtimeService(self.redis)
                await realtime.enqueue_scoring(return_req.id, order.merchant_id, order.customer_id, order.id)
            except Exception as exc:
                logger.warning("Realtime enqueue failed for return %s: %s", return_req.id, exc)

        fraud_score, fraud_decision = await self._fraud_score_for_return(return_req.id)
        refund_amount = await self._refunded_amount_for_return(return_req.id)
        detail = await self.get_return_detail(return_req.id)
        detail.fraud_risk_score = fraud_score
        detail.fraud_decision = fraud_decision
        detail.refund_amount = refund_amount
        detail.items = persisted_items
        return detail

    async def get_returns_by_order(self, order_id: UUID) -> list[OrderReturnRead]:
        order = await self._load_order(order_id)
        result = await self.session.execute(
            select(ReturnRequest).where(ReturnRequest.order_id == order.id).order_by(ReturnRequest.created_at.desc())
        )
        returns = result.scalars().all()
        items: list[OrderReturnRead] = []
        for return_req in returns:
            fraud_score, fraud_decision = await self._fraud_score_for_return(return_req.id)
            refund_amount = await self._refunded_amount_for_return(return_req.id)
            item_rows = await self.session.execute(select(ReturnItem).where(ReturnItem.return_id == return_req.id))
            return_items = [
                ReturnItemRead.model_validate(row)
                for row in item_rows.scalars().all()
            ]
            items.append(
                OrderReturnRead(
                    id=return_req.id,
                    external_return_id=return_req.external_return_id,
                    order_id=return_req.order_id,
                    merchant_id=return_req.merchant_id,
                    customer_id=return_req.customer_id,
                    created_by=return_req.created_by,
                    return_reason_category=return_req.return_reason_category,
                    return_reason=return_req.return_reason,
                    detailed_description=return_req.detailed_description,
                    condition_reported=return_req.condition_reported,
                    return_method=return_req.return_method,
                    pickup_address_id=return_req.pickup_address_id,
                    preferred_refund_method=return_req.preferred_refund_method,
                    return_status=return_req.return_status,
                    fraud_screening_status=return_req.fraud_screening_status,
                    eligibility_override=bool(return_req.eligibility_override),
                    eligibility_override_reason=return_req.eligibility_override_reason,
                    return_date=return_req.return_date,
                    hours_after_delivery=float(return_req.hours_after_delivery) if return_req.hours_after_delivery is not None else None,
                    created_at=return_req.created_at,
                    updated_at=return_req.updated_at,
                    fraud_risk_score=fraud_score,
                    fraud_decision=fraud_decision,
                    refund_amount=refund_amount,
                    item_count=len(return_items),
                    items=return_items,
                )
            )
        return items

    async def get_return_detail(self, return_id: UUID) -> ReturnDetailRead:
        return_req = await self.session.get(ReturnRequest, return_id)
        if not return_req:
            raise ReturnValidationError("RETURN_NOT_FOUND", "Return not found", 404)

        order = await self._load_order(return_req.order_id)
        customer = await self._load_customer(return_req.customer_id)
        shipment = await self._load_shipment(return_req.order_id)
        eligibility = await self.check_order_return_eligibility(return_req.order_id, can_override=True)
        return_items_result = await self.session.execute(select(ReturnItem).where(ReturnItem.return_id == return_req.id))
        return_items = [
            ReturnItemRead.model_validate(item)
            for item in return_items_result.scalars().all()
        ]
        fraud_score, fraud_decision = await self._fraud_score_for_return(return_req.id)
        refund_amount = await self._refunded_amount_for_return(return_req.id)
        timeline = [
            {"label": "Return created", "time": return_req.created_at.isoformat()},
        ]
        if return_req.updated_at:
            timeline.append({"label": "Return updated", "time": return_req.updated_at.isoformat()})
        audit_rows = await self.session.execute(
            select(AuditEvent)
            .where(AuditEvent.entity_type == "return_request", AuditEvent.entity_id == return_req.id)
            .order_by(AuditEvent.created_at.asc())
        )
        for event in audit_rows.scalars().all():
            timeline.append(
                {
                    "label": event.event_type.replace("_", " ").title(),
                    "time": event.created_at.isoformat(),
                }
            )
        return ReturnDetailRead(
            id=return_req.id,
            external_return_id=return_req.external_return_id,
            order_id=return_req.order_id,
            merchant_id=return_req.merchant_id,
            customer_id=return_req.customer_id,
            created_by=return_req.created_by,
            return_reason_category=return_req.return_reason_category,
            return_reason=return_req.return_reason,
            detailed_description=return_req.detailed_description,
            condition_reported=return_req.condition_reported,
            return_method=return_req.return_method,
            pickup_address_id=return_req.pickup_address_id,
            preferred_refund_method=return_req.preferred_refund_method,
            return_status=return_req.return_status,
            fraud_screening_status=return_req.fraud_screening_status,
            eligibility_override=bool(return_req.eligibility_override),
            eligibility_override_reason=return_req.eligibility_override_reason,
            return_date=return_req.return_date,
            hours_after_delivery=float(return_req.hours_after_delivery) if return_req.hours_after_delivery is not None else None,
            created_at=return_req.created_at,
            updated_at=return_req.updated_at,
            fraud_risk_score=fraud_score,
            fraud_decision=fraud_decision,
            refund_amount=refund_amount,
            item_count=len(return_items),
            items=return_items,
            order={
                "id": order.id,
                "merchant_id": order.merchant_id,
                "customer_id": order.customer_id,
                "external_order_id": order.external_order_id,
                "sku": order.sku,
                "product_name": order.product_name,
                "category": order.category,
                "product_value": float(order.product_value) if order.product_value is not None else None,
                "quantity": order.quantity,
                "payment_method": order.payment_method,
                "order_status": order.order_status,
                "order_date": order.order_date,
                "delivery_date": order.delivery_date,
                "product_image_url": order.product_image_url,
                "delivery_image_url": order.delivery_image_url,
            },
            customer={
                "id": customer.id if customer else None,
                "name": customer.name if customer else None,
                "email_hash": customer.email_hash if customer else None,
                "account_age_days": customer.account_age_days if customer else None,
            },
            eligibility=eligibility,
            timeline=timeline,
        )
