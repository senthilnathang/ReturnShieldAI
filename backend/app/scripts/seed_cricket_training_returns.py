#!/usr/bin/env python3
"""Seed a small cricket-ball return training set.

This script keeps the existing 100 cricket production orders and adds 10
curated return requests with different defect conditions for OCR and fraud
training.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sqlalchemy import delete, select as sa_select

from backend.app.core.database import async_session_factory
from backend.app.core.logging import setup_logging
from backend.app.prod_models import AuditEvent as ProdAuditEvent
from backend.app.prod_models import Customer as ProdCustomer
from backend.app.prod_models import FraudCase as ProdFraudCase
from backend.app.prod_models import FraudScore as ProdFraudScore
from backend.app.prod_models import Order as ProdOrder
from backend.app.prod_models import Refund as ProdRefund
from backend.app.prod_models import ReturnItem as ProdReturnItem
from backend.app.prod_models import ReturnRequest as ProdReturnRequest
from backend.app.prod_models import Shipment as ProdShipment
from backend.app.prod_models import SupportInteraction as ProdSupportInteraction
from backend.app.scripts.seed_cricket_returns import (
    CRICKET_MERCHANT_NAME,
    PROD_PREFIX,
    _cleanup_legacy_cricket_rows,
    _get_or_create_merchant,
    _seed_prod_orders,
    ensure_schema,
)

logger = logging.getLogger("returnshield.scripts.seed_cricket_training_returns")
TRAINING_RETURN_COUNT = 10


@dataclass(slots=True)
class TrainingReturnSpec:
    condition_reported: str
    return_reason_category: str
    return_reason: str
    detailed_description: str
    return_method: str
    pickup_address_id: str | None
    preferred_refund_method: str
    risk_level: str
    decision: str
    final_score: int
    case_status: str
    priority: str
    case_summary: str
    recommended_action: str
    support_subject: str
    support_message: str
    refund_multiplier: Decimal
    item_match_status: str


TRAINING_SPECS: list[TrainingReturnSpec] = [
    TrainingReturnSpec(
        condition_reported="seam_split",
        return_reason_category="DAMAGED_PRODUCT",
        return_reason="Seam split near the shoulder seam",
        detailed_description="The cricket ball seam split open during the first over. The customer attached a clear image showing the tear near the stitched seam.",
        return_method="PICKUP",
        pickup_address_id="cricket-training-pickup-001",
        preferred_refund_method="ORIGINAL_PAYMENT",
        risk_level="HIGH",
        decision="HOLD_REFUND_HIGH_RISK",
        final_score=92,
        case_status="OPEN",
        priority="HIGH",
        case_summary="Visible seam split with strong image evidence and a high-risk complaint pattern.",
        recommended_action="Hold refund and escalate for manual inspection.",
        support_subject="Cricket ball return - seam split",
        support_message="OCR/vision notes: seam split visible near the stitched seam. Customer requests pickup return.",
        refund_multiplier=Decimal("0.00"),
        item_match_status="MISMATCHED",
    ),
    TrainingReturnSpec(
        condition_reported="uneven_seam",
        return_reason_category="DEFECTIVE_PRODUCT",
        return_reason="Uneven seam and wobble while bowling",
        detailed_description="The seam is uneven around the circumference, causing wobble and inconsistent bounce. Customer shared a photo and said the ball does not feel regulation-ready.",
        return_method="COURIER_SELF_SHIP",
        pickup_address_id=None,
        preferred_refund_method="ORIGINAL_PAYMENT",
        risk_level="MEDIUM",
        decision="MANUAL_REVIEW",
        final_score=74,
        case_status="OPEN",
        priority="MEDIUM",
        case_summary="Uneven seam complaint with moderate fraud indicators and no refund request yet.",
        recommended_action="Inspect ball curvature and seam alignment before refunding.",
        support_subject="Cricket ball return - uneven seam",
        support_message="OCR/vision notes: uneven seam detected. Customer reports wobble during bowling.",
        refund_multiplier=Decimal("0.00"),
        item_match_status="FLAGGED",
    ),
    TrainingReturnSpec(
        condition_reported="shine_gone",
        return_reason_category="PRODUCT_NOT_AS_DESCRIBED",
        return_reason="Leather shine gone on arrival",
        detailed_description="The ball arrived with a dull finish and the expected shine was missing. The customer says the product looks older than advertised but there is no structural defect.",
        return_method="COURIER_SELF_SHIP",
        pickup_address_id=None,
        preferred_refund_method="ORIGINAL_PAYMENT",
        risk_level="LOW",
        decision="AUTO_APPROVE",
        final_score=29,
        case_status="CLOSED",
        priority="LOW",
        case_summary="Cosmetic complaint with low fraud signals and a straightforward return path.",
        recommended_action="Auto-approve and issue refund after basic inspection.",
        support_subject="Cricket ball return - shine gone",
        support_message="OCR/vision notes: the finish is dull; no seam damage visible.",
        refund_multiplier=Decimal("1.00"),
        item_match_status="MATCHED",
    ),
    TrainingReturnSpec(
        condition_reported="loose_stitching",
        return_reason_category="DEFECTIVE_PRODUCT",
        return_reason="Loose stitching around the seam",
        detailed_description="Several stitches are loose and lifting near the seam line. The customer asked for an inspection because the ball may split during use.",
        return_method="PICKUP",
        pickup_address_id="cricket-training-pickup-002",
        preferred_refund_method="ORIGINAL_PAYMENT",
        risk_level="HIGH",
        decision="HOLD_REFUND_HIGH_RISK",
        final_score=87,
        case_status="OPEN",
        priority="HIGH",
        case_summary="Loose stitching with a clear defect pattern and elevated risk.",
        recommended_action="Hold refund and escalate to quality review.",
        support_subject="Cricket ball return - loose stitching",
        support_message="OCR/vision notes: loose stitches visible along the seam line.",
        refund_multiplier=Decimal("0.00"),
        item_match_status="MISMATCHED",
    ),
    TrainingReturnSpec(
        condition_reported="water_damage",
        return_reason_category="DAMAGED_PRODUCT",
        return_reason="Water damage after delivery",
        detailed_description="The ball was left in wet packaging and the leather shows swelling and staining. The customer included an image showing water marks on the surface.",
        return_method="PICKUP",
        pickup_address_id="cricket-training-pickup-003",
        preferred_refund_method="ORIGINAL_PAYMENT",
        risk_level="HIGH",
        decision="HOLD_REFUND_HIGH_RISK",
        final_score=95,
        case_status="OPEN",
        priority="HIGH",
        case_summary="Clear water damage with severe cosmetic and material degradation.",
        recommended_action="Escalate immediately and block refund until inspection completes.",
        support_subject="Cricket ball return - water damage",
        support_message="OCR/vision notes: water staining and surface swelling detected on the leather.",
        refund_multiplier=Decimal("0.00"),
        item_match_status="MISMATCHED",
    ),
    TrainingReturnSpec(
        condition_reported="scuffed_leather",
        return_reason_category="DAMAGED_PRODUCT",
        return_reason="Scuffed leather surface",
        detailed_description="The surface has minor scuff marks but no seam failure. The customer believes the ball is still usable but wants a replacement because of the cosmetic damage.",
        return_method="COURIER_SELF_SHIP",
        pickup_address_id=None,
        preferred_refund_method="ORIGINAL_PAYMENT",
        risk_level="LOW",
        decision="AUTO_APPROVE",
        final_score=34,
        case_status="CLOSED",
        priority="LOW",
        case_summary="Minor cosmetic scuffs with low fraud risk.",
        recommended_action="Approve after quick surface inspection.",
        support_subject="Cricket ball return - scuffed leather",
        support_message="OCR/vision notes: surface scuffs only; no seam or shape defect visible.",
        refund_multiplier=Decimal("1.00"),
        item_match_status="MATCHED",
    ),
    TrainingReturnSpec(
        condition_reported="discoloration",
        return_reason_category="PRODUCT_NOT_AS_DESCRIBED",
        return_reason="Unexpected discoloration on delivery",
        detailed_description="The ball has a darker patch and the leather color is uneven across the panel. The customer says the product does not match the catalog images.",
        return_method="COURIER_SELF_SHIP",
        pickup_address_id=None,
        preferred_refund_method="ORIGINAL_PAYMENT",
        risk_level="MEDIUM",
        decision="MANUAL_REVIEW",
        final_score=56,
        case_status="OPEN",
        priority="MEDIUM",
        case_summary="Color mismatch complaint with moderate risk signals.",
        recommended_action="Review catalog match and surface condition before deciding.",
        support_subject="Cricket ball return - discoloration",
        support_message="OCR/vision notes: discoloration visible across multiple panels.",
        refund_multiplier=Decimal("0.00"),
        item_match_status="FLAGGED",
    ),
    TrainingReturnSpec(
        condition_reported="cracked_surface",
        return_reason_category="DAMAGED_PRODUCT",
        return_reason="Cracked leather surface",
        detailed_description="A crack runs through the outer leather layer and the customer says the ball opened up after a short net session. The image shows a clear surface fracture.",
        return_method="PICKUP",
        pickup_address_id="cricket-training-pickup-004",
        preferred_refund_method="ORIGINAL_PAYMENT",
        risk_level="HIGH",
        decision="HOLD_REFUND_HIGH_RISK",
        final_score=90,
        case_status="OPEN",
        priority="HIGH",
        case_summary="Surface crack indicates a severe product defect.",
        recommended_action="Inspect immediately and hold refund until QA completes.",
        support_subject="Cricket ball return - cracked surface",
        support_message="OCR/vision notes: a clear crack is visible in the leather surface.",
        refund_multiplier=Decimal("0.00"),
        item_match_status="MISMATCHED",
    ),
    TrainingReturnSpec(
        condition_reported="misshapen",
        return_reason_category="DEFECTIVE_PRODUCT",
        return_reason="Ball arrived misshapen",
        detailed_description="The ball does not sit evenly on the table and appears misshapen on one side. The customer reported irregular bounce immediately after unboxing.",
        return_method="COURIER_SELF_SHIP",
        pickup_address_id=None,
        preferred_refund_method="ORIGINAL_PAYMENT",
        risk_level="MEDIUM",
        decision="MANUAL_REVIEW",
        final_score=63,
        case_status="OPEN",
        priority="MEDIUM",
        case_summary="Shape defect with moderate fraud indicators.",
        recommended_action="Check roundness and seam alignment before refund.",
        support_subject="Cricket ball return - misshapen",
        support_message="OCR/vision notes: ball appears misshapen and not perfectly spherical.",
        refund_multiplier=Decimal("0.00"),
        item_match_status="FLAGGED",
    ),
    TrainingReturnSpec(
        condition_reported="packaging_damaged",
        return_reason_category="DAMAGED_PRODUCT",
        return_reason="Packaging damaged and ball scratched",
        detailed_description="The outer box was damaged and the ball shows minor scratches on arrival. The customer asked for a replacement because the item did not arrive in collectible condition.",
        return_method="COURIER_SELF_SHIP",
        pickup_address_id=None,
        preferred_refund_method="ORIGINAL_PAYMENT",
        risk_level="LOW",
        decision="AUTO_APPROVE",
        final_score=41,
        case_status="CLOSED",
        priority="LOW",
        case_summary="Packaging damage only, with low risk and a clear return path.",
        recommended_action="Approve replacement after standard inspection.",
        support_subject="Cricket ball return - packaging damaged",
        support_message="OCR/vision notes: packaging damage visible with minor surface scratches.",
        refund_multiplier=Decimal("1.00"),
        item_match_status="MATCHED",
    ),
]


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def _cleanup_prod_training_rows(session) -> int:
    order_ids = [
        row[0]
        for row in (
            await session.execute(
                sa_select(ProdOrder.id).where(ProdOrder.external_order_id.like(f"{PROD_PREFIX}%"))
            )
        ).all()
    ]
    if not order_ids:
        return 0

    return_ids = [
        row[0]
        for row in (
            await session.execute(sa_select(ProdReturnRequest.id).where(ProdReturnRequest.order_id.in_(order_ids)))
        ).all()
    ]
    if not return_ids:
        return 0

    await session.execute(delete(ProdSupportInteraction).where(ProdSupportInteraction.return_id.in_(return_ids)))
    await session.execute(delete(ProdRefund).where(ProdRefund.return_id.in_(return_ids)))
    await session.execute(delete(ProdFraudCase).where(ProdFraudCase.return_id.in_(return_ids)))
    await session.execute(delete(ProdFraudScore).where(ProdFraudScore.return_id.in_(return_ids)))
    await session.execute(delete(ProdReturnItem).where(ProdReturnItem.return_id.in_(return_ids)))
    await session.execute(
        delete(ProdAuditEvent).where(
            ProdAuditEvent.entity_type == "return_request",
            ProdAuditEvent.entity_id.in_(return_ids),
        )
    )
    await session.execute(delete(ProdReturnRequest).where(ProdReturnRequest.id.in_(return_ids)))
    await session.commit()
    logger.info("Removed %s production cricket training returns", len(return_ids))
    return len(return_ids)


async def _seed_training_returns() -> int:
    await _seed_prod_orders()

    async with async_session_factory() as session:
        merchant = await _get_or_create_merchant(session)
        orders_result = await session.execute(
            sa_select(ProdOrder)
            .where(ProdOrder.external_order_id.like(f"{PROD_PREFIX}%"))
            .order_by(ProdOrder.external_order_id.asc())
            .limit(TRAINING_RETURN_COUNT)
        )
        orders = orders_result.scalars().all()
        if len(orders) < TRAINING_RETURN_COUNT:
            raise RuntimeError(f"Expected at least {TRAINING_RETURN_COUNT} cricket orders, found {len(orders)}")

        await _cleanup_prod_training_rows(session)

        orders_result = await session.execute(
            sa_select(ProdOrder)
            .where(ProdOrder.external_order_id.like(f"{PROD_PREFIX}%"))
            .order_by(ProdOrder.external_order_id.asc())
            .limit(TRAINING_RETURN_COUNT)
        )
        orders = orders_result.scalars().all()

        created = 0
        now = datetime.now(timezone.utc)
        for idx, (order, spec) in enumerate(zip(orders, TRAINING_SPECS, strict=True), start=1):
            shipment_result = await session.execute(
                sa_select(ProdShipment).where(ProdShipment.order_id == order.id).limit(1)
            )
            shipment = shipment_result.scalar_one_or_none()

            customer = await session.get(ProdCustomer, order.customer_id)
            if customer is None:
                raise RuntimeError(f"Missing customer for order {order.id}")

            return_created_at = now - timedelta(days=idx, hours=idx * 2)
            hours_after_delivery = round((return_created_at - order.delivery_date).total_seconds() / 3600, 2) if order.delivery_date else None

            return_request = ProdReturnRequest(
                merchant_id=merchant.id,
                customer_id=order.customer_id,
                order_id=order.id,
                shipment_id=shipment.id if shipment else None,
                external_return_id=f"RET-CRICKET-TRAIN-{idx:03d}",
                created_by="seed:cricket-training",
                return_reason_category=spec.return_reason_category,
                return_reason=spec.return_reason,
                detailed_description=spec.detailed_description,
                condition_reported=spec.condition_reported,
                return_method=spec.return_method,
                pickup_address_id=spec.pickup_address_id,
                preferred_refund_method=spec.preferred_refund_method,
                return_status="APPROVED" if spec.decision == "AUTO_APPROVE" else "UNDER_REVIEW",
                fraud_screening_status="COMPLETED",
                eligibility_override=False,
                eligibility_override_reason=None,
                return_channel="CRICKET_TRAINING",
                return_date=return_created_at,
                hours_after_delivery=hours_after_delivery,
                created_at=return_created_at,
                updated_at=return_created_at,
            )
            session.add(return_request)
            await session.flush()

            session.add(
                ProdReturnItem(
                    return_id=return_request.id,
                    order_id=order.id,
                    sku=order.sku,
                    product_name=order.product_name,
                    category=order.category,
                    quantity=1,
                    product_value=order.product_value,
                    declared_condition=spec.condition_reported,
                    warehouse_condition="INSPECTED",
                    serial_number_hash=None,
                    imei_hash=None,
                    item_match_status=spec.item_match_status,
                )
            )

            score_value = spec.final_score
            session.add(
                ProdFraudScore(
                    merchant_id=merchant.id,
                    return_id=return_request.id,
                    customer_id=order.customer_id,
                    rule_score=min(100, score_value - 8),
                    structured_ml_score=min(100, score_value - 4),
                    nlp_score=min(100, score_value - 12),
                    graph_score=min(100, score_value - 20),
                    anomaly_score=min(100, score_value - 16),
                    final_score=score_value,
                    risk_level=spec.risk_level,
                    decision=spec.decision,
                    reason_codes_json=[
                        "CRICKET_TRAINING",
                        spec.condition_reported.upper(),
                        spec.decision,
                    ],
                    score_breakdown_json={
                        "condition_reported": spec.condition_reported,
                        "return_reason_category": spec.return_reason_category,
                        "support_subject": spec.support_subject,
                    },
                )
            )

            session.add(
                ProdFraudCase(
                    merchant_id=merchant.id,
                    return_id=return_request.id,
                    customer_id=order.customer_id,
                    case_status=spec.case_status,
                    priority=spec.priority,
                    assigned_to="fraud.ops@returnshield.ai",
                    recommended_action=spec.recommended_action,
                    case_summary=spec.case_summary,
                )
            )

            if spec.refund_multiplier > 0:
                refund_amount = round(Decimal(str(order.product_value or 0)) * spec.refund_multiplier, 2)
                session.add(
                    ProdRefund(
                        merchant_id=merchant.id,
                        return_id=return_request.id,
                        customer_id=order.customer_id,
                        refund_method=spec.preferred_refund_method,
                        refund_account_hash=_hash(f"refund-{idx:03d}"),
                        refund_amount=refund_amount,
                        refund_status="COMPLETED",
                        refund_date=return_created_at + timedelta(hours=6),
                    )
                )

            session.add(
                ProdSupportInteraction(
                    merchant_id=merchant.id,
                    customer_id=order.customer_id,
                    return_id=return_request.id,
                    channel="portal",
                    subject=spec.support_subject,
                    message_text=spec.support_message,
                    message_embedding_id=f"cricket-training-{idx:03d}",
                    sentiment_score=-0.780 + (idx * 0.031),
                    urgency_score=0.650 + (idx * 0.020),
                )
            )
            session.add(
                ProdAuditEvent(
                    merchant_id=merchant.id,
                    entity_type="return_request",
                    entity_id=return_request.id,
                    event_type="RETURN_REQUEST_CREATED",
                    event_json={
                        "order_id": str(order.id),
                        "condition_reported": spec.condition_reported,
                        "return_reason_category": spec.return_reason_category,
                        "created_by": "seed:cricket-training",
                    },
                )
            )
            session.add(
                ProdAuditEvent(
                    merchant_id=merchant.id,
                    entity_type="return_request",
                    entity_id=return_request.id,
                    event_type="RETURN_SCORING_QUEUED",
                    event_json={
                        "return_id": str(return_request.id),
                        "decision": spec.decision,
                        "final_score": score_value,
                    },
                )
            )
            session.add(
                ProdAuditEvent(
                    merchant_id=merchant.id,
                    entity_type="return_request",
                    entity_id=return_request.id,
                    event_type="RETURN_STATUS_CHANGED",
                    event_json={
                        "status": "APPROVED" if spec.decision == "AUTO_APPROVE" else "UNDER_REVIEW",
                        "case_status": spec.case_status,
                    },
                )
            )
            created += 1

            if idx % 5 == 0:
                await session.commit()
                logger.info("Seeded %s cricket training returns", idx)

        await session.commit()
        logger.info("Seeded %s cricket training returns for merchant %s", created, CRICKET_MERCHANT_NAME)
        return created


async def main() -> None:
    setup_logging()
    ensure_schema()
    _cleanup_legacy_cricket_rows()
    await _seed_training_returns()


if __name__ == "__main__":
    asyncio.run(main())
