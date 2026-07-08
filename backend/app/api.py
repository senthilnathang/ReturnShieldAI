from __future__ import annotations
import time

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlmodel import Session, select

from backend.app.core.config import settings
from backend.app.db.session import get_session, init_db
from backend.app.ml.explainability import build_explainability_panel
from backend.app.ml.sample_data_generator import seed_database
from backend.app.ml.train import ModelBundle, train_models
from backend.app.models import AnalystFeedback, Customer, FraudScore, ModelTrainingRun, Order, ReturnCase, ReturnRecord, Rule
from backend.app.rules.engine import RuleEngine
from backend.app.modules.routes import router as modules_router
from backend.app.schemas.common import (
    AnalystDecisionPayload,
    CaseDetail,
    CaseSummary,
    FeedbackRead,
    MetricsResponse,
    ReturnScoreResponse,
    RuleCreate,
    RuleRead,
    RuleUpdate,
    ScoreRequest,
    ScoreBreakdown,
)
from backend.app.services.scoring_service import ScoringService


def _customer_risk_details(session: Session, customer: Customer) -> tuple[float, list[dict[str, Any]]]:
    service = ScoringService(RuleEngine([]), models=None)
    stats = service._get_customer_stats(session, customer)
    return service._customer_risk_score(customer, stats)


router = APIRouter(prefix="/api")
MODEL_BUNDLE = None


def _serialize_rule(rule: Rule) -> dict[str, Any]:
    return {
        "id": rule.id,
        "name": rule.name,
        "description": rule.description,
        "condition": rule.condition,
        "score": rule.score,
        "enabled": rule.enabled,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
    }


def _load_models(session: Session) -> ModelBundle:
    global MODEL_BUNDLE
    if MODEL_BUNDLE is None:
        MODEL_BUNDLE = train_models(session)
    return MODEL_BUNDLE


def _load_rule_engine(session: Session) -> RuleEngine:
    rules = session.exec(select(Rule)).all()
    return RuleEngine([_serialize_rule(rule) for rule in rules])


def _decode_fraud_payload(score: FraudScore) -> tuple[list[str], dict[str, Any]]:
    decoded = json.loads(score.reason_codes_json) if score.reason_codes_json else []
    if isinstance(decoded, dict):
        return list(decoded.get("reason_codes", [])), dict(decoded.get("advanced_signals", {}))
    return list(decoded), {}


@router.post("/returns", response_model=ReturnScoreResponse)
@router.post("/returns/score", response_model=ReturnScoreResponse)
def create_return(payload: ScoreRequest, session: Session = Depends(get_session)):
    models = _load_models(session)
    service = ScoringService(_load_rule_engine(session), models)
    artifacts = service.score_payload(session, payload)
    return ReturnScoreResponse(
        return_id=artifacts.return_record.id,
        case_id=artifacts.case.id,
        customer_risk_score=artifacts.customer_risk_score,
        risk_score=artifacts.case.risk_score,
        risk_level=artifacts.case.risk_level,
        decision=artifacts.case.decision,
        recommended_action=artifacts.case.recommended_action,
        score_breakdown=ScoreBreakdown(**artifacts.score_breakdown),
        reason_codes=artifacts.reason_codes,
        explanation=artifacts.explanation,
        decision_trace=artifacts.decision_trace,
        explainability=artifacts.explainability,
        advanced_signals=artifacts.advanced_signals,
        model_version=artifacts.model_version,
    )


@router.get("/cases", response_model=list[CaseSummary])
def list_cases(session: Session = Depends(get_session), q: str | None = None, decision: str | None = None, risk_level: str | None = None):
    stmt = (
        select(ReturnCase, ReturnRecord, Customer, Order)
        .join(ReturnRecord, ReturnCase.return_id == ReturnRecord.id)
        .join(Customer, ReturnRecord.customer_id == Customer.id)
        .join(Order, ReturnRecord.order_id == Order.id)
        .order_by(ReturnCase.created_at.desc())
    )
    rows = session.exec(stmt).all()
    cases: list[CaseSummary] = []
    for case, return_record, customer, order in rows:
        if q:
            haystack = " ".join(
                [
                    str(case.id),
                    customer.name,
                    order.product_name,
                    return_record.return_reason,
                    order.sku,
                ]
            ).lower()
            if q.lower() not in haystack:
                continue
        if decision and case.decision != decision:
            continue
        if risk_level and case.risk_level != risk_level:
            continue
        customer_risk_score, _ = _customer_risk_details(session, customer)
        cases.append(
            CaseSummary(
                id=case.id,
                return_id=case.return_id,
                customer_name=customer.name,
                product_name=order.product_name,
                return_reason=return_record.return_reason,
                customer_risk_score=customer_risk_score,
                risk_score=case.risk_score,
                risk_level=case.risk_level,
                decision=case.decision,
                status=case.status,
                created_at=case.created_at,
            )
        )
    return cases


@router.get("/cases/{case_id}", response_model=CaseDetail)
def get_case(case_id: UUID, session: Session = Depends(get_session)):
    stmt = (
        select(ReturnCase, ReturnRecord, Customer, Order, FraudScore)
        .join(ReturnRecord, ReturnCase.return_id == ReturnRecord.id)
        .join(Customer, ReturnRecord.customer_id == Customer.id)
        .join(Order, ReturnRecord.order_id == Order.id)
        .join(FraudScore, FraudScore.return_id == ReturnRecord.id)
        .where(ReturnCase.id == case_id)
    )
    row = session.exec(stmt).first()
    if not row:
        raise HTTPException(status_code=404, detail="Case not found")
    case, return_record, customer, order, score = row
    feedback = session.exec(select(AnalystFeedback).where(AnalystFeedback.case_id == case.id)).first()
    customer_risk_score, decision_trace = _customer_risk_details(session, customer)
    timeline = [
        {"label": "Return created", "time": return_record.created_at.isoformat()},
        {"label": "Case scored", "time": case.created_at.isoformat()},
    ]
    if feedback:
        timeline.append({"label": "Analyst feedback", "time": feedback.created_at.isoformat()})
    reason_codes, advanced_signals = _decode_fraud_payload(score)
    explainability = build_explainability_panel(
        score_breakdown={
            "rule_score": score.rule_score,
            "structured_ml_score": score.structured_ml_score,
            "nlp_score": score.nlp_score,
            "anomaly_score": score.anomaly_score,
        },
        customer_risk_score=customer_risk_score,
        reason_codes=reason_codes,
        decision=case.decision,
    )
    return CaseDetail(
        id=case.id,
        return_id=case.return_id,
        customer_name=customer.name,
        product_name=order.product_name,
        return_reason=return_record.return_reason,
        customer_risk_score=customer_risk_score,
        risk_score=case.risk_score,
        risk_level=case.risk_level,
        decision=case.decision,
        status=case.status,
        created_at=case.created_at,
        customer={
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "account_age_days": customer.account_age_days,
            "address": customer.address,
            "device_id": customer.device_id,
            "lifetime_orders": customer.lifetime_orders,
            "lifetime_returns": customer.lifetime_returns,
        },
        order={
            "sku": order.sku,
            "product_name": order.product_name,
            "category": order.category,
            "product_value": order.product_value,
            "expected_weight": order.expected_weight,
            "payment_method": order.payment_method,
            "payment_method_risk_score": order.payment_method_risk_score,
            "delivery_date": order.delivery_date,
            "delivery_status": order.delivery_status,
        },
        return_data={
            "return_reason": return_record.return_reason,
            "chat_transcript": return_record.chat_transcript,
            "email_text": return_record.email_text,
            "returned_weight": return_record.returned_weight,
            "condition_reported": return_record.condition_reported,
        },
        score_breakdown=ScoreBreakdown(
            rule_score=score.rule_score,
            structured_ml_score=score.structured_ml_score,
            nlp_score=score.nlp_score,
            anomaly_score=score.anomaly_score,
        ),
        reason_codes=reason_codes,
        explanation=score.explanation,
        recommended_action=case.recommended_action,
        decision_trace=decision_trace + [
            {"stage": "rule_score", "value": score.rule_score},
            {"stage": "structured_ml_score", "value": score.structured_ml_score},
            {"stage": "nlp_score", "value": score.nlp_score},
            {"stage": "anomaly_score", "value": score.anomaly_score},
            {"stage": "final_score", "value": case.risk_score},
        ],
        explainability=explainability,
        advanced_signals=advanced_signals,
        timeline=timeline,
    )


@router.patch("/cases/{case_id}/decision")
def update_case_decision(case_id: UUID, payload: AnalystDecisionPayload, session: Session = Depends(get_session)):
    case = session.get(ReturnCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    case.decision = payload.decision
    case.status = payload.status or ("CLOSED" if payload.decision in {"AUTO_APPROVE", "REJECT_RETURN", "Mark Confirmed Fraud"} else "OPEN")
    case.assigned_to = payload.assigned_to or case.assigned_to
    case.updated_at = datetime.utcnow()
    session.add(case)
    if payload.confirmed_label or payload.notes:
        session.add(
            AnalystFeedback(
                case_id=case.id,
                analyst_decision=payload.decision,
                confirmed_label=payload.confirmed_label or payload.decision.lower(),
                notes=payload.notes,
            )
        )
    session.commit()
    return {"ok": True, "case_id": str(case.id), "decision": case.decision, "status": case.status}


@router.get("/dashboard/metrics", response_model=MetricsResponse)
def dashboard_metrics(session: Session = Depends(get_session)):
    start_of_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    total_returns = session.exec(select(func.count(ReturnRecord.id)).where(ReturnRecord.created_at >= start_of_day)).one()
    high_risk = session.exec(select(func.count(ReturnCase.id)).where(ReturnCase.risk_level == "HIGH")).one()
    manual = session.exec(select(func.count(ReturnCase.id)).where(ReturnCase.decision == "MANUAL_REVIEW")).one()
    auto = session.exec(select(func.count(ReturnCase.id)).where(ReturnCase.decision == "AUTO_APPROVE")).one()
    open_cases = session.exec(select(func.count(ReturnCase.id)).where(ReturnCase.status == "OPEN")).one()
    avg_risk = session.exec(select(func.avg(ReturnCase.risk_score))).one() or 0
    fraud_prevented = round(float(high_risk) * 211.0, 2)
    return_value_at_risk = round(float(high_risk) * 180.0, 2)
    risk_buckets = [
        {"label": "Low", "value": session.exec(select(func.count(ReturnCase.id)).where(ReturnCase.risk_score < 40)).one()},
        {"label": "Medium", "value": session.exec(select(func.count(ReturnCase.id)).where(ReturnCase.risk_score >= 40, ReturnCase.risk_score < 70)).one()},
        {"label": "High", "value": session.exec(select(func.count(ReturnCase.id)).where(ReturnCase.risk_score >= 70)).one()},
    ]
    status_buckets = [
        {"label": "Open", "value": open_cases},
        {"label": "Closed", "value": session.exec(select(func.count(ReturnCase.id)).where(ReturnCase.status == "CLOSED")).one()},
    ]
    fraud_types = [
        {"label": "Weight mismatch", "value": session.exec(select(func.count(FraudScore.id)).where(FraudScore.explanation.contains("weight"))).one()},
        {"label": "Shared address/device", "value": session.exec(select(func.count(FraudScore.id)).where(FraudScore.explanation.contains("Shared"))).one()},
        {"label": "Text/script reuse", "value": session.exec(select(func.count(FraudScore.id)).where(FraudScore.reason_codes_json.contains("SCRIPT"))).one()},
    ]
    value_at_risk = [
        {"label": "Approved", "value": float(auto) * 180.0},
        {"label": "Manual Review", "value": float(manual) * 320.0},
        {"label": "High Risk", "value": return_value_at_risk},
    ]
    model_run = session.exec(select(ModelTrainingRun).order_by(ModelTrainingRun.completed_at.desc())).first()
    return MetricsResponse(
        totals={
            "total_returns_today": int(total_returns),
            "high_risk_cases": int(high_risk),
            "manual_review_cases": int(manual),
            "auto_approved_returns": int(auto),
            "estimated_fraud_prevented": fraud_prevented,
            "average_risk_score": round(float(avg_risk or 0), 2),
            "return_value_at_risk": return_value_at_risk,
        },
        charts={
            "risk_distribution": risk_buckets,
            "fraud_types": fraud_types,
            "cases_by_status": status_buckets,
            "return_value_at_risk": value_at_risk,
        },
        model={
            "model_version": model_run.model_version if model_run else "v0-seeded",
            "last_training_time": model_run.completed_at.isoformat() if model_run else None,
            "precision": model_run.precision if model_run else 0.0,
            "recall": model_run.recall if model_run else 0.0,
            "f1": model_run.f1 if model_run else 0.0,
            "labels_collected": model_run.labels_collected if model_run else 0,
        },
    )


@router.get("/rules", response_model=list[RuleRead])
def get_rules(session: Session = Depends(get_session)):
    return [RuleRead(**_serialize_rule(rule)) for rule in session.exec(select(Rule).order_by(Rule.created_at.asc())).all()]

@router.get("/feedback", response_model=list[FeedbackRead])
def list_feedback(session: Session = Depends(get_session)):
    stmt = (
        select(AnalystFeedback, Customer, Order, ReturnCase)
        .join(ReturnCase, AnalystFeedback.case_id == ReturnCase.id)
        .join(ReturnRecord, ReturnCase.return_id == ReturnRecord.id)
        .join(Customer, ReturnRecord.customer_id == Customer.id)
        .join(Order, ReturnRecord.order_id == Order.id)
        .order_by(AnalystFeedback.created_at.desc())
    )
    rows = session.exec(stmt).all()
    items: list[FeedbackRead] = []
    for feedback, customer, order, case in rows:
        items.append(
            FeedbackRead(
                id=feedback.id,
                case_id=feedback.case_id,
                analyst_decision=feedback.analyst_decision,
                confirmed_label=feedback.confirmed_label,
                notes=feedback.notes,
                created_at=feedback.created_at,
                customer_name=customer.name,
                product_name=order.product_name,
                risk_score=case.risk_score,
                risk_level=case.risk_level,
            )
        )
    return items


@router.post("/rules", response_model=RuleRead)
def create_rule(payload: RuleCreate, session: Session = Depends(get_session)):
    rule = Rule(**payload.model_dump())
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return RuleRead(**_serialize_rule(rule))


@router.patch("/rules/{rule_id}", response_model=RuleRead)
def patch_rule(rule_id: UUID, payload: RuleUpdate, session: Session = Depends(get_session)):
    rule = session.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, key, value)
    rule.updated_at = datetime.utcnow()
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return RuleRead(**_serialize_rule(rule))


@router.post("/ml/retrain")
def retrain_models(session: Session = Depends(get_session)):
    global MODEL_BUNDLE
    bundle = train_models(session)
    MODEL_BUNDLE = bundle
    return {"ok": True, "model_version": bundle.version, "metrics": bundle.metrics}


@router.get("/health")
def health(session: Session = Depends(get_session)):
    return {"status": "ok"}


@router.post("/seed")
def trigger_seed(session: Session = Depends(get_session)):
    from backend.app.modules.seed_data import seed_all_module_data

    results = seed_all_module_data(session)
    return {"seeded": True, "results": {k: v for k, v in results.items() if isinstance(v, (int, bool, str))}}


@router.get("/modules/dashboard")
def modules_dashboard(session: Session = Depends(get_session)):
    from backend.app.modules.model_registry import ModelRegistry
    from backend.app.modules.monitoring_engine.monitoring_engine import MonitoringEngine
    from backend.app.modules.vector_engine.embedding_service import EmbeddingService
    from backend.app.modules.merchant_engine.merchant_engine import MerchantEngine
    from backend.app.modules.alert_engine.alert_engine import AlertEngine

    registry = ModelRegistry()
    monitor = MonitoringEngine()
    embedding = EmbeddingService()
    merchants = MerchantEngine()
    alerts = AlertEngine()

    model_status = {}
    for cat in ["structured", "nlp", "graph", "anomaly", "fusion"]:
        current = registry.get_current_version(cat)
        model_status[cat] = {"current_version": current, "versions": len(registry.list_versions(cat))}

    return {
        "embeddings": {"size": embedding.size(), "active_model": embedding.provider.model_name if hasattr(embedding.provider, 'model_name') else "tf-idf"},
        "models": model_status,
        "monitoring": monitor.get_performance_summary(),
        "merchants": {"count": len(merchants.list_merchants()), "ids": merchants.list_merchants()},
        "alert_rules": len(alerts.rules),
    }


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174", "http://localhost:3000", "http://127.0.0.1:3000"],
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    app.include_router(modules_router)

    @app.on_event("startup")
    def startup():
        from backend.app.db.session import Session, engine

        last_error = None
        for _ in range(15):
            try:
                init_db()
                with Session(engine) as session:
                    seed_database(session)
                    global MODEL_BUNDLE
                    MODEL_BUNDLE = train_models(session)
                    from backend.app.modules.seed_data import seed_all_module_data
                    seed_result = seed_all_module_data(session)
                    print(f"[startup] Module seed complete: {seed_result.get('embeddings', 0)} embeddings, {seed_result.get('investigations', 0)} investigations")
                return
            except Exception as exc:
                last_error = exc
                time.sleep(2)
        raise last_error

    return app
