from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlmodel import Session, select

from backend.app.ml.advanced_signals import build_advanced_signals
from backend.app.ml.explainability import build_explainability_panel, build_explanation, recommended_action
from backend.app.ml.feature_engineering import build_features, text_features
from backend.app.ml.fusion_engine import decision_from_score, fuse_scores
from backend.app.models import Customer, FraudScore, Order, ReturnCase, ReturnRecord
from backend.app.rules.engine import RuleEngine


@dataclass
class ScoreArtifacts:
    customer: Customer
    order: Order
    return_record: ReturnRecord
    case: ReturnCase
    fraud_score: FraudScore
    score_breakdown: dict[str, float]
    reason_codes: list[str]
    explanation: str
    customer_risk_score: float
    decision_trace: list[dict[str, str | float]]
    explainability: dict[str, Any]
    advanced_signals: dict[str, Any]
    model_version: str | None = None


class ScoringService:
    def __init__(self, rule_engine: RuleEngine, models: Any):
        self.rule_engine = rule_engine
        self.models = models

    def _get_customer_stats(self, session: Session, customer: Customer) -> dict[str, Any]:
        returns = session.exec(select(ReturnRecord).where(ReturnRecord.customer_id == customer.id)).all()
        recent_30d = [row for row in returns if row.return_date >= datetime.utcnow() - timedelta(days=30)]
        recent_90d = [row for row in returns if row.return_date >= datetime.utcnow() - timedelta(days=90)]
        same_address = session.exec(select(Customer).where(Customer.address == customer.address)).all()
        same_device = session.exec(select(Customer).where(Customer.device_id == customer.device_id)).all()
        chargeback_count = session.exec(
            select(func.count(ReturnCase.id))
            .join(ReturnRecord, ReturnCase.return_id == ReturnRecord.id)
            .where(ReturnRecord.customer_id == customer.id, ReturnCase.decision == "HOLD_REFUND_HIGH_RISK")
        ).one()
        previous_fraud_count = session.exec(
            select(func.count(FraudScore.id))
            .join(ReturnRecord, FraudScore.return_id == ReturnRecord.id)
            .where(ReturnRecord.customer_id == customer.id, FraudScore.final_score >= 70)
        ).one()
        return {
            "customer_return_count_30d": len(recent_30d),
            "orders_30d": max(len(recent_30d) + 1, 1),
            "return_rate_30d": len(recent_30d) / max(customer.lifetime_orders or 1, 1),
            "return_rate_90d": len(recent_90d) / max(customer.lifetime_orders or 1, 1),
            "address_reuse_count": max(0, len(same_address) - 1),
            "same_device_account_count": max(0, len(same_device) - 1),
            "previous_fraud_count": int(previous_fraud_count),
            "chargeback_count": int(chargeback_count),
        }

    def _customer_risk_score(self, customer: Customer, stats: dict[str, Any]) -> tuple[float, list[dict[str, str | float]]]:
        components = [
            ("recent_return_velocity", min(float(stats.get("customer_return_count_30d", 0)) * 8.0, 40.0)),
            ("address_reuse", min(float(stats.get("address_reuse_count", 0)) * 10.0, 20.0)),
            ("device_sharing", min(float(stats.get("same_device_account_count", 0)) * 12.0, 24.0)),
            ("prior_fraud", min(float(stats.get("previous_fraud_count", 0)) * 18.0, 36.0)),
            ("chargeback_pressure", min(float(stats.get("chargeback_count", 0)) * 15.0, 30.0)),
        ]
        base = max(0.0, 18.0 - float(customer.account_age_days) / 45.0)
        score = min(100.0, round(base + sum(value for _, value in components), 2))
        trace = [{"stage": name, "value": round(value, 2)} for name, value in components]
        trace.insert(0, {"stage": "base_new_account_risk", "value": round(base, 2)})
        trace.append({"stage": "customer_risk_score", "value": score})
        return score, trace

    def score_payload(self, session: Session, payload) -> ScoreArtifacts:
        customer = self._resolve_customer(session, payload.customer.model_dump())
        order = self._create_order(session, customer, payload.order.model_dump())
        return_record = self._create_return(session, customer, order, payload.return_data.model_dump())

        stats = self._get_customer_stats(session, customer)
        customer_risk_score, customer_risk_trace = self._customer_risk_score(customer, stats)
        features = build_features(customer, order, return_record, stats)
        features.update(text_features(return_record.return_reason))
        combined_text = " ".join(
            part for part in [return_record.return_reason, return_record.chat_transcript, return_record.email_text] if part
        )

        rule_score, rule_reasons, triggered_rules = self.rule_engine.evaluate(features)
        structured_score, structured_reasons = self.models.structured.score(features)
        structured_family_scores = self.models.structured.family_scores(features)
        nlp_analysis = self.models.nlp.analyze(combined_text, features)
        nlp_score = float(nlp_analysis["score"])
        flagged_phrases = nlp_analysis["flagged_phrases"]
        text_reason_codes = nlp_analysis["text_reason_codes"]
        anomaly_score, anomaly_reasons = self.models.anomaly.score(features)

        final_score = fuse_scores(rule_score, structured_score, nlp_score, anomaly_score)
        decision, risk_level, fallback_action = decision_from_score(final_score)

        reason_codes = []
        reason_codes.extend(rule_reasons)
        reason_codes.extend(structured_reasons)
        reason_codes.extend(flagged_phrases)
        reason_codes.extend(anomaly_reasons)
        reason_codes.extend(text_reason_codes)
        reason_codes = list(dict.fromkeys(reason_codes))[:8]

        explanation = build_explanation(
            reason_codes,
            {
                "prefix": f"This return is {risk_level.lower()} risk because",
                "fallback": "This return is low risk based on the current rule and model signals.",
            },
        )
        explainability = build_explainability_panel(
            score_breakdown={
                "rule_score": rule_score,
                "structured_ml_score": structured_score,
                "nlp_score": nlp_score,
                "anomaly_score": anomaly_score,
            },
            customer_risk_score=customer_risk_score,
            reason_codes=reason_codes,
            decision=decision,
        )
        case = ReturnCase(
            return_id=return_record.id,
            risk_score=final_score,
            risk_level=risk_level,
            decision=decision,
            status="OPEN" if decision != "AUTO_APPROVE" else "CLOSED",
            recommended_action=recommended_action(decision) or fallback_action,
            assigned_to="analyst.queue" if decision != "AUTO_APPROVE" else None,
        )
        session.add(case)
        session.flush()

        advanced_signals = build_advanced_signals(
            session,
            payload,
            customer,
            order,
            return_record,
            explanation=explanation,
            decision=decision,
            reason_codes=reason_codes,
            structured={"family_scores": structured_family_scores, "reasons": structured_reasons},
            nlp=nlp_analysis,
        )
        fraud_score = FraudScore(
            return_id=return_record.id,
            rule_score=rule_score,
            structured_ml_score=structured_score,
            nlp_score=nlp_score,
            anomaly_score=anomaly_score,
            final_score=final_score,
            reason_codes_json=json.dumps({"reason_codes": reason_codes, "advanced_signals": advanced_signals}),
            explanation=explanation,
        )
        session.add(fraud_score)
        session.commit()
        session.refresh(case)
        session.refresh(fraud_score)

        decision_trace = [
            {"stage": "customer_risk", "value": customer_risk_score},
            *customer_risk_trace,
            {"stage": "rule_engine", "value": round(rule_score, 2)},
            {"stage": "structured_ml", "value": round(structured_score, 2)},
            {"stage": "nlp_engine", "value": round(nlp_score, 2)},
            {"stage": "anomaly_engine", "value": round(anomaly_score, 2)},
            {"stage": "final_score", "value": final_score},
            {"stage": "decision", "value": decision},
        ]

        return ScoreArtifacts(
            customer=customer,
            order=order,
            return_record=return_record,
            case=case,
            fraud_score=fraud_score,
            score_breakdown={
                "rule_score": round(rule_score, 2),
                "structured_ml_score": round(structured_score, 2),
                "nlp_score": round(nlp_score, 2),
                "anomaly_score": round(anomaly_score, 2),
            },
            reason_codes=reason_codes,
            explanation=explanation,
            customer_risk_score=customer_risk_score,
            explainability=explainability,
            decision_trace=decision_trace,
            advanced_signals=advanced_signals,
            model_version=getattr(self.models, "version", None),
        )

    def _resolve_customer(self, session: Session, payload: dict[str, Any]) -> Customer:
        existing = session.exec(select(Customer).where(Customer.email == payload["email"])).first()
        if existing:
            existing.name = payload.get("name", existing.name)
            existing.phone = payload.get("phone", existing.phone)
            existing.account_age_days = payload.get("account_age_days", existing.account_age_days)
            existing.address = payload.get("address", existing.address)
            existing.device_id = payload.get("device_id", existing.device_id)
            existing.lifetime_orders = payload.get("lifetime_orders", existing.lifetime_orders)
            existing.lifetime_returns = payload.get("lifetime_returns", existing.lifetime_returns)
            session.add(existing)
            session.flush()
            return existing
        customer = Customer(**payload)
        session.add(customer)
        session.flush()
        return customer

    def _create_order(self, session: Session, customer: Customer, payload: dict[str, Any]) -> Order:
        order = Order(customer_id=customer.id, **payload)
        session.add(order)
        session.flush()
        return order

    def _create_return(self, session: Session, customer: Customer, order: Order, payload: dict[str, Any]) -> ReturnRecord:
        allowed_keys = {"return_reason", "chat_transcript", "email_text", "returned_weight", "condition_reported"}
        record_payload = {key: value for key, value in payload.items() if key in allowed_keys}
        record = ReturnRecord(customer_id=customer.id, order_id=order.id, **record_payload)
        session.add(record)
        session.flush()
        return record
