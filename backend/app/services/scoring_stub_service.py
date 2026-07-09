from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.prod_models.customer import Customer
from backend.app.prod_models.order import Order
from backend.app.prod_models.shipment import Shipment
from backend.app.prod_models.return_request import ReturnRequest
from backend.app.prod_models.payment import Payment
from backend.app.prod_models.refund import Refund
from backend.app.prod_models.fraud_score import FraudScore
from backend.app.prod_models.fraud_case import FraudCase
from backend.app.prod_models.support_interaction import SupportInteraction
from app.core.config import settings
from app.schemas.return_schema import ScoringResult

logger = logging.getLogger("returnshield.scoring")


class ScoringStubService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def score_return(self, return_id: UUID) -> ScoringResult:
        return_req = await self.session.get(ReturnRequest, return_id)
        if not return_req:
            raise ValueError(f"Return {return_id} not found")

        customer = await self.session.get(Customer, return_req.customer_id)
        order = await self.session.get(Order, return_req.order_id)
        shipment = await self.session.get(Shipment, return_req.shipment_id) if return_req.shipment_id else None

        payment_query = select(Payment).where(Payment.order_id == return_req.order_id)
        payment = (await self.session.execute(payment_query)).scalar_one_or_none()

        refund_query = select(Refund).where(Refund.return_id == return_id)
        refund = (await self.session.execute(refund_query)).scalar_one_or_none()

        support_query = select(SupportInteraction).where(SupportInteraction.return_id == return_id)
        support = (await self.session.execute(support_query)).scalar_one_or_none()

        reason_codes = []
        score = 0

        # Rule 1: High return frequency
        return_count_query = select(func.count(ReturnRequest.id)).where(
            ReturnRequest.customer_id == return_req.customer_id,
            ReturnRequest.created_at >= datetime.now(timezone.utc).replace(day=1),
        )
        monthly_returns = (await self.session.execute(return_count_query)).scalar() or 0
        if monthly_returns >= 3:
            score += 25
            reason_codes.append("High return frequency")

        # Rule 2: High product value
        if order and order.product_value and float(order.product_value) > 200:
            score += 15
            reason_codes.append("High product value")

        # Rule 3: Weight mismatch
        if shipment and shipment.weight_difference is not None and abs(float(shipment.weight_difference)) > 0.2:
            score += 20
            reason_codes.append("Weight mismatch")

        # Rule 4: Quick return after delivery
        if return_req.hours_after_delivery is not None and float(return_req.hours_after_delivery) < 48:
            score += 15
            reason_codes.append("Quick return after delivery")

        # Rule 5: Chargeback history
        if payment and payment.chargeback_flag:
            score += 20
            reason_codes.append("Chargeback history")

        # Rule 6: Same refund account reused
        if refund:
            same_account_query = select(func.count(Refund.id)).where(
                Refund.refund_account_hash == refund.refund_account_hash,
                Refund.id != refund.id,
            )
            same_count = (await self.session.execute(same_account_query)).scalar() or 0
            if same_count > 2:
                score += 15
                reason_codes.append("Refund account reuse")

        # Rule 7: Suspicious return text
        if support and support.message_text:
            suspicious = ["empty box", "never received", "chargeback", "refund now", "fake",
                         "didn't order", "wrong item", "scam", "fraud", "missing items",
                         "stolen", "damaged", "not as described", "wrong size"]
            msg_lower = support.message_text.lower()
            matches = [w for w in suspicious if w in msg_lower]
            if len(matches) >= 2:
                score += 10
                reason_codes.append("Suspicious return text")

        # Rule 8: Customer risk
        if customer and customer.customer_risk_score > 50:
            score += 10
            reason_codes.append("High-risk customer profile")

        # New account
        if customer and customer.account_age_days < 30:
            score += 5
            reason_codes.append("New account")

        # Finalize
        final_score = min(100, max(0, score))

        if final_score < settings.default_risk_threshold_low:
            risk_level = "LOW"
            decision = "AUTO_APPROVE"
        elif final_score < settings.default_risk_threshold_high:
            risk_level = "MEDIUM"
            decision = "MANUAL_REVIEW"
        else:
            risk_level = "HIGH"
            decision = "HOLD_REFUND_HIGH_RISK"

        return ScoringResult(
            rule_score=final_score,
            final_score=final_score,
            risk_level=risk_level,
            decision=decision,
            reason_codes=reason_codes,
            score_breakdown={
                "return_frequency": min(25, monthly_returns * 8),
                "product_value_risk": min(15, 15 if order and order.product_value and float(order.product_value) > 200 else 0),
                "weight_mismatch": min(20, 20 if shipment and shipment.weight_difference and abs(float(shipment.weight_difference)) > 0.2 else 0),
                "quick_return": min(15, 15 if return_req.hours_after_delivery and float(return_req.hours_after_delivery) < 48 else 0),
                "chargeback_risk": min(20, 20 if payment and payment.chargeback_flag else 0),
            },
        )

    async def save_score_and_case(self, return_id: UUID, result: ScoringResult) -> tuple[FraudScore, Optional[FraudCase]]:
        return_req = await self.session.get(ReturnRequest, return_id)

        score_record = FraudScore(
            merchant_id=return_req.merchant_id,
            return_id=return_id,
            customer_id=return_req.customer_id,
            rule_score=result.rule_score,
            structured_ml_score=result.structured_ml_score,
            nlp_score=result.nlp_score,
            graph_score=result.graph_score,
            anomaly_score=result.anomaly_score,
            final_score=result.final_score,
            risk_level=result.risk_level,
            decision=result.decision,
            reason_codes_json={"reason_codes": result.reason_codes},
            score_breakdown_json=result.score_breakdown,
        )
        self.session.add(score_record)
        await self.session.flush()

        fraud_case = None
        if result.final_score >= settings.default_risk_threshold_low:
            fraud_case = FraudCase(
                merchant_id=return_req.merchant_id,
                return_id=return_id,
                customer_id=return_req.customer_id,
                fraud_score_id=score_record.id,
                case_status="OPEN",
                priority="HIGH" if result.final_score >= settings.default_risk_threshold_high else "MEDIUM",
                recommended_action=result.decision,
                case_summary=", ".join(result.reason_codes[:5]),
            )
            self.session.add(fraud_case)
            await self.session.flush()

        return score_record, fraud_case
