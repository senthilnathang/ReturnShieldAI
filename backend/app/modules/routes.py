from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from backend.app.core.config import settings
from backend.app.db.session import get_session
from backend.app.ml.fusion_engine import fuse_scores, decision_from_score
from backend.app.models import (
    AnalystFeedback, Customer, FraudScore, ModelTrainingRun,
    Order, ReturnCase, ReturnRecord, Rule,
)
from backend.app.modules.alert_engine.alert_engine import AlertEngine
from backend.app.modules.evidence_engine.evidence_engine import EvidenceEngine
from backend.app.modules.fraud_patterns import FRAUD_PATTERNS, get_pattern_by_id, match_patterns
from backend.app.modules.graph_engine.graph_intelligence import (
    build_enhanced_fraud_graph, extract_enhanced_graph_features,
)
from backend.app.modules.investigation_engine.investigation_engine import InvestigationEngine
from backend.app.modules.merchant_engine.merchant_engine import MerchantEngine
from backend.app.modules.model_registry import ModelRegistry
from backend.app.modules.monitoring_engine.monitoring_engine import MonitoringEngine
from backend.app.modules.nlp_engine.nlp_intelligence import NLPIntelligenceEngine
from backend.app.modules.shap_explainability import ShapExplainabilityEngine
from backend.app.modules.timeline_engine.timeline_engine import TimelineEngine
from backend.app.modules.vector_engine.embedding_service import EmbeddingService

router = APIRouter(prefix="/api")

_embedding_service: EmbeddingService | None = None
_evidence_engine = EvidenceEngine()
_timeline_engine = TimelineEngine()
_merchant_engine = MerchantEngine()
_alert_engine = AlertEngine()
_monitoring_engine = MonitoringEngine()
_investigation_engine = InvestigationEngine()
_model_registry = ModelRegistry()


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


@router.post("/embeddings/search")
def search_embeddings(payload: dict[str, Any], session: Session = Depends(get_session)):
    text = payload.get("text", "")
    k = payload.get("k", 20)
    if not text.strip():
        raise HTTPException(status_code=400, detail="text is required")
    service = get_embedding_service()
    results = service.search_similar(text, k=k)
    return {"query": text, "results": results, "total": len(results)}


@router.post("/embeddings/index")
def index_cases(session: Session = Depends(get_session)):
    stmt = select(ReturnCase, ReturnRecord, Customer).join(ReturnRecord, ReturnCase.return_id == ReturnRecord.id).join(Customer, ReturnRecord.customer_id == Customer.id)
    rows = session.exec(stmt).all()
    texts = []
    metadata = []
    for case, return_record, customer in rows:
        combined = " ".join(filter(None, [return_record.return_reason, return_record.chat_transcript, return_record.email_text]))
        if combined.strip():
            texts.append(combined)
            metadata.append({
                "case_id": str(case.id),
                "customer_name": customer.name,
                "decision": case.decision,
                "risk_level": case.risk_level,
                "risk_score": case.risk_score,
                "return_reason": return_record.return_reason,
            })
    service = get_embedding_service()
    service.add_cases(texts, metadata)
    return {"indexed": len(texts), "total_in_store": service.size()}


@router.get("/embeddings/stats")
def embedding_stats():
    service = get_embedding_service()
    return {"size": service.size(), "active_model": service.provider.model_name, "dim": service.provider.dim}


@router.post("/embeddings/clear")
def clear_embeddings():
    service = get_embedding_service()
    service.clear()
    return {"ok": True, "size": 0}


@router.post("/nlp/analyze")
def nlp_analyze(payload: dict[str, Any]):
    text = payload.get("text", "")
    if not text.strip():
        raise HTTPException(status_code=400, detail="text is required")
    engine = NLPIntelligenceEngine()
    result = engine.analyze(text)
    return {"text": text[:200], "analysis": result}


@router.get("/graph/case/{case_id}")
def case_graph(case_id: UUID, session: Session = Depends(get_session)):
    stmt = select(ReturnCase, ReturnRecord, Customer, Order).join(ReturnRecord, ReturnCase.return_id == ReturnRecord.id).join(Customer, ReturnRecord.customer_id == Customer.id).join(Order, ReturnRecord.order_id == Order.id).where(ReturnCase.id == case_id)
    row = session.exec(stmt).first()
    if not row:
        raise HTTPException(status_code=404, detail="Case not found")
    case, return_record, customer, order = row
    all_customers = session.exec(select(Customer)).all()
    all_orders = session.exec(select(Order)).all()
    all_returns = session.exec(select(ReturnRecord)).all()
    feedbacks = session.exec(select(AnalystFeedback).where(AnalystFeedback.confirmed_label == "confirmed_fraud")).all()
    confirmed = {fb.case_id for fb in feedbacks}
    confirmed_cases = session.exec(select(ReturnCase).where(ReturnCase.id.in_(confirmed))).all()
    confirmed_customer_ids = set()
    for c in confirmed_cases:
        ret = session.get(ReturnRecord, c.return_id)
        if ret:
            confirmed_customer_ids.add(ret.customer_id)
    graph_data = build_enhanced_fraud_graph(all_customers, all_orders, all_returns, confirmed_customer_ids)
    features = extract_enhanced_graph_features(graph_data, customer.id, return_record.id)
    return {"case_id": str(case.id), "graph_features": features}


@router.get("/graph/summary")
def graph_summary(session: Session = Depends(get_session)):
    customers = session.exec(select(Customer)).all()
    orders = session.exec(select(Order)).all()
    returns = session.exec(select(ReturnRecord)).all()
    feedbacks = session.exec(select(AnalystFeedback).where(AnalystFeedback.confirmed_label == "confirmed_fraud")).all()
    confirmed_cases = session.exec(select(ReturnCase).where(ReturnCase.id.in_({fb.case_id for fb in feedbacks}))).all()
    confirmed = set()
    for c in confirmed_cases:
        ret = session.get(ReturnRecord, c.return_id)
        if ret:
            confirmed.add(ret.customer_id)
    graph_data = build_enhanced_fraud_graph(customers, orders, returns, confirmed)
    g = graph_data.graph
    import networkx as nx
    components = list(nx.connected_components(g))
    customer_components = [len([n for n in comp if str(n).startswith("customer:")]) for comp in components]
    return {
        "total_nodes": g.number_of_nodes(),
        "total_edges": g.number_of_edges(),
        "graph_density": round(nx.density(g), 4),
        "components": len(components),
        "customer_clusters": [s for s in customer_components if s > 1],
        "largest_cluster": max(customer_components) if customer_components else 0,
        "confirmed_fraud_customers": len(confirmed),
    }


@router.post("/evidence")
def generate_evidence(payload: dict[str, Any]):
    evidence = _evidence_engine.build_evidence(
        score_breakdown=payload.get("scores", {}),
        reason_codes=payload.get("reason_codes", []),
        advanced_signals=payload.get("advanced_signals", {}),
        customer_risk_score=payload.get("customer_risk_score", 0),
        flagged_phrases=payload.get("flagged_phrases"),
    )
    return {"evidence": evidence, "total": len(evidence)}


@router.get("/timeline/{case_id}")
def case_timeline(case_id: UUID, session: Session = Depends(get_session)):
    stmt = select(ReturnCase, ReturnRecord, Customer, Order).join(ReturnRecord, ReturnCase.return_id == ReturnRecord.id).join(Customer, ReturnRecord.customer_id == Customer.id).join(Order, ReturnRecord.order_id == Order.id).where(ReturnCase.id == case_id)
    row = session.exec(stmt).first()
    if not row:
        raise HTTPException(status_code=404, detail="Case not found")
    case, return_record, customer, order = row
    feedback = session.exec(select(AnalystFeedback).where(AnalystFeedback.case_id == case.id)).first()
    timeline = _timeline_engine.build_timeline(customer, order, return_record, case, feedback)
    return {"case_id": str(case.id), "events": timeline, "total": len(timeline)}


@router.get("/investigation/{case_id}")
def investigation_report(case_id: UUID, session: Session = Depends(get_session)):
    stmt = select(ReturnCase, ReturnRecord, Customer, Order, FraudScore).join(ReturnRecord, ReturnCase.return_id == ReturnRecord.id).join(Customer, ReturnRecord.customer_id == Customer.id).join(Order, ReturnRecord.order_id == Order.id).join(FraudScore, FraudScore.return_id == ReturnRecord.id).where(ReturnCase.id == case_id)
    row = session.exec(stmt).first()
    if not row:
        raise HTTPException(status_code=404, detail="Case not found")
    case, return_record, customer, order, score = row
    import json as j
    reason_codes_raw = j.loads(score.reason_codes_json) if score.reason_codes_json else {}
    reason_codes = reason_codes_raw if isinstance(reason_codes_raw, list) else reason_codes_raw.get("reason_codes", [])
    advanced_signals = reason_codes_raw if isinstance(reason_codes_raw, dict) else {}
    feedback = session.exec(select(AnalystFeedback).where(AnalystFeedback.case_id == case.id)).first()
    crs_score = 0.0
    evidence = _evidence_engine.build_evidence(
        {"rule_score": score.rule_score, "structured_ml_score": score.structured_ml_score,
         "nlp_score": score.nlp_score, "anomaly_score": score.anomaly_score},
        reason_codes, advanced_signals, crs_score,
    )
    timeline = _timeline_engine.build_timeline(customer, order, return_record, case, feedback)
    report = _investigation_engine.generate_report({
        "evidence": evidence, "graph_fraud": advanced_signals.get("graph_fraud", {}),
        "advanced_signals": advanced_signals, "scores": {"final_score": case.risk_score,
            "rule_score": score.rule_score, "structured_ml_score": score.structured_ml_score,
            "nlp_score": score.nlp_score, "anomaly_score": score.anomaly_score},
        "timeline": timeline, "reason_codes": reason_codes,
        "case_id": str(case.id), "customer_name": customer.name,
        "risk_score": case.risk_score, "product_value": order.product_value,
        "is_vip": False, "previous_fraud_count": 0,
        "customer_risk_score": 0,
    })
    return {"case_id": str(case.id), "investigation": report}


@router.get("/patterns")
def list_patterns():
    return {"patterns": FRAUD_PATTERNS, "total": len(FRAUD_PATTERNS)}


@router.get("/patterns/{pattern_id}")
def get_pattern(pattern_id: str):
    pattern = get_pattern_by_id(pattern_id)
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")
    return {"pattern": pattern}


@router.post("/patterns/match")
def match_case_patterns(payload: dict[str, Any]):
    matches = match_patterns(payload)
    return {"matches": matches}


@router.get("/merchants")
def list_merchants():
    return {"merchants": _merchant_engine.list_merchants()}


@router.get("/merchants/{merchant_id}")
def get_merchant(merchant_id: str):
    config = _merchant_engine.get_config(merchant_id)
    return {"merchant_id": merchant_id, "config": config}


@router.post("/merchants/{merchant_id}")
def update_merchant(merchant_id: str, payload: dict[str, Any]):
    _merchant_engine.save_config(merchant_id, payload)
    return {"ok": True, "merchant_id": merchant_id}


@router.get("/models")
def list_models():
    categories = ["structured", "nlp", "graph", "anomaly", "fusion"]
    result = {}
    for cat in categories:
        versions = _model_registry.list_versions(cat)
        current = _model_registry.get_current_version(cat)
        result[cat] = {"versions": versions, "current": current}
    return {"models": result}


@router.post("/models/{category}/save")
def save_model(category: str, payload: dict[str, Any]):
    version = _model_registry.save(category, payload.get("model"), payload.get("metadata", {}))
    return {"ok": True, "category": category, "version": version}


@router.post("/models/{category}/rollback/{version}")
def rollback_model(category: str, version: str):
    success = _model_registry.rollback(category, version)
    if not success:
        raise HTTPException(status_code=404, detail=f"Version {version} not found in {category}")
    return {"ok": True, "category": category, "version": version}


@router.get("/monitoring/performance")
def monitoring_performance():
    return _monitoring_engine.get_performance_summary()


@router.get("/monitoring/drift")
def check_drift():
    return {"drift_checked": True, "message": "Send reference and current datasets to check drift. Use POST /monitoring/drift/check"}


@router.post("/monitoring/drift/check")
def check_data_drift(payload: dict[str, Any]):
    import pandas as pd
    ref = payload.get("reference")
    cur = payload.get("current")
    if not ref or not cur:
        raise HTTPException(status_code=400, detail="reference and current data required")
    ref_df = pd.DataFrame(ref)
    cur_df = pd.DataFrame(cur)
    _monitoring_engine.drift_monitor.set_reference(ref_df)
    report = _monitoring_engine.check_data_drift(cur_df)
    return {
        "drift_detected": report.drift_detected,
        "drift_share": report.drift_share,
        "drifted_columns": report.drifted_columns,
        "timestamp": report.timestamp,
    }


@router.post("/alerts/evaluate")
def evaluate_alerts(payload: dict[str, Any]):
    fired = _alert_engine.evaluate_and_alert(payload)
    return {"alerts_fired": fired, "total": len(fired)}


@router.get("/alerts/rules")
def list_alert_rules():
    return {"rules": [{"name": r.name, "description": r.description, "severity": r.severity, "providers": r.providers} for r in _alert_engine.rules]}


# --- Kaggle Import Routes ---

@router.get("/kaggle/datasets")
def kaggle_list_datasets():
    from backend.app.modules.kaggle_import.importer import KAGGLE_DATASETS_CATALOG
    return {"datasets": KAGGLE_DATASETS_CATALOG, "total": len(KAGGLE_DATASETS_CATALOG)}


@router.post("/kaggle/import")
def kaggle_import(payload: dict[str, Any], session: Session = Depends(get_session)):
    dataset_id = payload.get("dataset_id", "")
    batch_size = payload.get("batch_size", 250)
    max_rows = payload.get("max_rows", 5000)
    if not dataset_id:
        raise HTTPException(status_code=400, detail="dataset_id is required")

    from backend.app.modules.kaggle_import.importer import import_from_kaggle_id

    result = import_from_kaggle_id(session, dataset_id, batch_size=batch_size, max_rows=max_rows)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.post("/kaggle/import/local")
def kaggle_import_local(payload: dict[str, Any], session: Session = Depends(get_session)):
    path = payload.get("path", "")
    batch_size = payload.get("batch_size", 250)
    max_rows = payload.get("max_rows", 5000)
    if not path:
        raise HTTPException(status_code=400, detail="path is required")

    from backend.app.modules.kaggle_import.importer import import_dataset

    result = import_dataset(session, path, batch_size=batch_size, max_rows=max_rows)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result
