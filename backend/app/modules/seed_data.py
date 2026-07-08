from __future__ import annotations

import json
import os
import random
from datetime import datetime, timedelta
from typing import Any

import networkx as nx
import numpy as np
from sqlmodel import Session, select

from backend.app.models import (
    AnalystFeedback,
    Customer,
    FraudScore,
    Order,
    ReturnCase,
    ReturnRecord,
)
from backend.app.modules.alert_engine.alert_engine import AlertEngine
from backend.app.modules.evidence_engine.evidence_engine import EvidenceEngine
from backend.app.modules.fraud_patterns import match_patterns
from backend.app.modules.fusion_engine.fusion_engine import FusionEngine
from backend.app.modules.graph_engine.graph_intelligence import (
    build_enhanced_fraud_graph,
)
from backend.app.modules.investigation_engine.investigation_engine import (
    InvestigationEngine,
)
from backend.app.modules.merchant_engine.merchant_engine import MerchantEngine
from backend.app.modules.model_registry import ModelRegistry
from backend.app.modules.monitoring_engine.monitoring_engine import (
    MonitoringEngine,
)
from backend.app.modules.shap_explainability import ShapExplainabilityEngine
from backend.app.modules.timeline_engine.timeline_engine import TimelineEngine
from backend.app.modules.vector_engine.embedding_service import EmbeddingService

SEEDED_FLAG = "_module_data_seeded"
SAMPLE_MODEL_DATA: dict[str, Any] = {
    "feature_importance": {
        "lifetime_returns": 0.18,
        "product_value": 0.14,
        "return_rate_30d": 0.16,
        "weight_difference": 0.12,
        "payment_method_risk_score": 0.09,
        "hours_after_delivery": 0.08,
        "address_reuse_count": 0.07,
        "chargeback_count": 0.06,
        "previous_fraud_count": 0.05,
        "same_device_account_count": 0.05,
    },
    "n_supported_trees": 100,
    "clustering_k": 8,
    "anomaly_threshold": 0.75,
}


def _get_random_case_data(session: Session) -> list[dict[str, Any]]:
    stmt = (
        select(ReturnCase, ReturnRecord, Customer, Order, FraudScore)
        .join(ReturnRecord, ReturnCase.return_id == ReturnRecord.id)
        .join(Customer, ReturnRecord.customer_id == Customer.id)
        .join(Order, ReturnRecord.order_id == Order.id)
        .join(FraudScore, FraudScore.return_id == ReturnRecord.id)
        .limit(10)
    )
    rows = session.exec(stmt).all()
    results = []
    for case, return_record, customer, order, score in rows:
        reason_codes = json.loads(score.reason_codes_json) if score.reason_codes_json else []
        results.append({
            "case": case, "return_record": return_record, "customer": customer,
            "order": order, "score": score, "reason_codes": reason_codes,
        })
    return results


def seed_embeddings(session: Session) -> int:
    service = EmbeddingService()
    if service.size() > 0:
        return 0
    stmt = select(ReturnCase, ReturnRecord, Customer).join(
        ReturnRecord, ReturnCase.return_id == ReturnRecord.id
    ).join(Customer, ReturnRecord.customer_id == Customer.id).limit(50)
    rows = session.exec(stmt).all()
    texts = []
    metadata = []
    for case, return_record, customer in rows:
        combined = " ".join(filter(None, [
            return_record.return_reason,
            return_record.chat_transcript,
            return_record.email_text,
        ]))
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
    if texts:
        service.add_cases(texts, metadata)
    return len(texts)


def seed_model_registry() -> None:
    registry = ModelRegistry()
    categories = ["structured", "nlp", "graph", "anomaly", "fusion"]
    metadata_templates = {
        "structured": {"accuracy": 0.86, "precision": 0.82, "recall": 0.79, "f1": 0.80, "training_date": "2026-06-15"},
        "nlp": {"accuracy": 0.84, "precision": 0.81, "recall": 0.77, "f1": 0.79, "training_date": "2026-06-14"},
        "graph": {"accuracy": 0.79, "precision": 0.84, "recall": 0.72, "f1": 0.77, "training_date": "2026-06-13"},
        "anomaly": {"accuracy": 0.81, "precision": 0.78, "recall": 0.85, "f1": 0.81, "training_date": "2026-06-12"},
        "fusion": {"accuracy": 0.88, "precision": 0.85, "recall": 0.83, "f1": 0.84, "training_date": "2026-06-15"},
    }
    for cat in categories:
        if registry.get_current_version(cat):
            continue
        meta = metadata_templates.get(cat, {})
        registry.save(cat, SAMPLE_MODEL_DATA, {
            **meta, "description": f"Seed {cat} model",
            "features": list(SAMPLE_MODEL_DATA.get("feature_importance", {}).keys()),
        })


def seed_monitoring() -> None:
    monitor = MonitoringEngine()
    perf = monitor.get_performance_summary()
    if perf.get("samples", 0) > 0:
        return

    now = datetime.utcnow()
    for i in range(50):
        timestamp = (now - timedelta(minutes=i * 30)).isoformat()
        features = {
            "rule_score": random.uniform(10, 90),
            "structured_ml_score": random.uniform(10, 90),
            "nlp_score": random.uniform(10, 90),
            "anomaly_score": random.uniform(10, 90),
        }
        prediction = random.uniform(10, 100)
        actual = prediction + random.uniform(-15, 15)
        latency = random.uniform(15, 180)
        monitor.performance_tracker.log_prediction(features, prediction, actual, latency)

    ref_data = [
        {"rule_score": 25, "structured_ml_score": 30, "nlp_score": 20, "anomaly_score": 15}
        for _ in range(100)
    ]
    import pandas as pd
    monitor.drift_monitor.set_reference(pd.DataFrame(ref_data))


def seed_alerts(session: Session) -> None:
    engine = AlertEngine()
    random.seed(42)
    case_data_list = _get_random_case_data(session)
    for item in case_data_list[:8]:
        case = item["case"]
        order = item["order"]
        customer = item["customer"]
        engine.evaluate_and_alert({
            "case_id": str(case.id),
            "risk_level": case.risk_level,
            "risk_score": case.risk_score,
            "customer_name": customer.name,
            "product_value": order.product_value,
            "customer_risk_score": 45.0,
            "is_vip": customer.lifetime_orders > 30,
            "previous_fraud_count": customer.lifetime_returns // 3,
            "graph_fraud": {"ring_risk_score": 60 if case.risk_level == "HIGH" else 10},
        })


def seed_graph_data(session: Session) -> dict[str, Any] | None:
    stmt = select(ReturnCase, ReturnRecord, Customer, Order).join(
        ReturnRecord, ReturnCase.return_id == ReturnRecord.id
    ).join(Customer, ReturnRecord.customer_id == Customer.id).join(
        Order, ReturnRecord.order_id == Order.id
    ).limit(20)
    rows = session.exec(stmt).all()
    if not rows:
        return None

    all_customers: list[Customer] = []
    all_orders: list[Order] = []
    all_returns: list[ReturnRecord] = []
    seen_customers: set[str] = set()
    for case, return_record, customer, order in rows:
        if customer.id not in seen_customers:
            seen_customers.add(customer.id)
            all_customers.append(customer)
        all_orders.append(order)
        all_returns.append(return_record)

    feedbacks = session.exec(
        select(AnalystFeedback).where(AnalystFeedback.confirmed_label == "confirmed_fraud")
    ).all()
    confirmed = {fb.case_id for fb in feedbacks}
    confirmed_cases = session.exec(
        select(ReturnCase).where(ReturnCase.id.in_(confirmed))
    ).all()
    confirmed_customer_ids = set()
    for c in confirmed_cases:
        ret = session.get(ReturnRecord, c.return_id)
        if ret:
            confirmed_customer_ids.add(ret.customer_id)

    graph_data = build_enhanced_fraud_graph(all_customers, all_orders, all_returns, confirmed_customer_ids)
    g = graph_data.graph
    if g.number_of_nodes() == 0:
        return None

    import networkx as nx
    components = list(nx.connected_components(g))
    nodes_by_component = []
    for comp in components:
        sub = g.subgraph(comp)
        customer_nodes = [n for n in comp if str(n).startswith("customer:")]
        if len(customer_nodes) < 2:
            continue
        try:
            pagerank = nx.pagerank(sub)
        except Exception:
            pagerank = {}
        try:
            from networkx.algorithms.community import louvain_communities
            communities = list(louvain_communities(sub, seed=42))
        except Exception:
            communities = []

        nodes_by_component.append({
            "size": len(comp),
            "customer_count": len(customer_nodes),
            "edge_count": sub.number_of_edges(),
            "density": round(nx.density(sub), 4),
            "top_nodes": sorted(
                [{"id": n, "pr": round(pagerank.get(n, 0), 4)} for n in customer_nodes],
                key=lambda x: x["pr"], reverse=True,
            )[:10],
            "community_count": len(communities),
        })

    return {
        "total_nodes": g.number_of_nodes(),
        "total_edges": g.number_of_edges(),
        "graph_density": round(nx.density(g), 4),
        "components": len(components),
        "nodes_by_component": nodes_by_component,
        "confirmed_fraud_customers": len(confirmed_customer_ids),
    }


def seed_investigations(session: Session) -> int:
    evidence_engine = EvidenceEngine()
    timeline_engine = TimelineEngine()
    investigation_engine = InvestigationEngine()
    case_data_list = _get_random_case_data(session)
    seeded = 0
    for item in case_data_list:
        case = item["case"]
        return_record = item["return_record"]
        customer = item["customer"]
        order = item["order"]
        score = item["score"]
        reason_codes = item["reason_codes"]
        feedback = session.exec(
            select(AnalystFeedback).where(AnalystFeedback.case_id == case.id)
        ).first()

        evidence = evidence_engine.build_evidence(
            score_breakdown={
                "rule_score": score.rule_score,
                "structured_ml_score": score.structured_ml_score,
                "nlp_score": score.nlp_score,
                "anomaly_score": score.anomaly_score,
            },
            reason_codes=reason_codes,
            advanced_signals={},
            customer_risk_score=45.0,
            flagged_phrases=["refund now", "chargeback", "empty box"],
        )

        timeline = timeline_engine.build_timeline(customer, order, return_record, case, feedback)

        report = investigation_engine.generate_report({
            "evidence": evidence,
            "graph_fraud": {},
            "advanced_signals": {},
            "scores": {
                "final_score": case.risk_score,
                "rule_score": score.rule_score,
                "structured_ml_score": score.structured_ml_score,
                "nlp_score": score.nlp_score,
                "anomaly_score": score.anomaly_score,
            },
            "timeline": timeline,
            "reason_codes": reason_codes,
            "case_id": str(case.id),
            "customer_name": customer.name,
            "risk_score": case.risk_score,
            "product_value": order.product_value,
            "is_vip": customer.lifetime_orders > 30,
            "previous_fraud_count": customer.lifetime_returns // 3,
            "customer_risk_score": 45.0,
        })
        if report:
            seeded += 1
    return seeded


def seed_merchant_configs() -> None:
    merchant_engine = MerchantEngine()
    existing = merchant_engine.list_merchants()
    if existing:
        return

    sample_configs = {
        "fashion": {
            "risk_thresholds": {"low": 35, "high": 65},
            "fusion_weights": {
                "rule_score": 0.20,
                "structured_ml_score": 0.25,
                "nlp_score": 0.25,
                "anomaly_score": 0.15,
                "graph_risk_score": 0.10,
                "customer_risk_score": 0.05,
            },
            "rules": {"weight_mismatch_threshold": 0.5, "max_return_rate": 0.3},
            "high_risk_categories": ["apparel", "footwear"],
            "analyst_assignee": "analyst.fashion",
        },
        "electronics": {
            "risk_thresholds": {"low": 40, "high": 70},
            "fusion_weights": {
                "rule_score": 0.30,
                "structured_ml_score": 0.30,
                "nlp_score": 0.15,
                "anomaly_score": 0.15,
                "graph_risk_score": 0.05,
                "customer_risk_score": 0.05,
            },
            "rules": {"weight_mismatch_threshold": 0.3, "max_return_rate": 0.25},
            "high_risk_categories": ["electronics"],
            "analyst_assignee": "analyst.electronics",
        },
        "luxury": {
            "risk_thresholds": {"low": 30, "high": 55},
            "fusion_weights": {
                "rule_score": 0.15,
                "structured_ml_score": 0.20,
                "nlp_score": 0.30,
                "anomaly_score": 0.20,
                "graph_risk_score": 0.10,
                "customer_risk_score": 0.05,
            },
            "rules": {"weight_mismatch_threshold": 0.2, "max_return_rate": 0.15},
            "high_risk_categories": ["luxury", "jewelry", "designer"],
            "analyst_assignee": "analyst.luxury",
        },
    }
    for mid, config in sample_configs.items():
        merchant_engine.save_config(mid, config)


def seed_shap_explainability() -> dict[str, Any]:
    engine = ShapExplainabilityEngine()
    sample_features = {
        "lifetime_returns": 8,
        "lifetime_orders": 12,
        "product_value": 420.0,
        "return_rate_30d": 0.45,
        "hours_after_delivery": 6,
        "expected_weight": 0.9,
        "returned_weight": 0.12,
        "weight_difference": 0.78,
        "payment_method_risk_score": 40,
        "chargeback_count": 2,
        "address_reuse_count": 3,
        "same_device_account_count": 2,
    }
    return engine.explain(sample_features)


def seed_fusion_engine() -> dict[str, Any]:
    engine = FusionEngine()
    sample_scores = {
        "rule_score": 65.0,
        "structured_ml_score": 78.0,
        "nlp_score": 84.0,
        "anomaly_score": 73.0,
        "graph_risk_score": 55.0,
        "customer_risk_score": 45.0,
    }
    return engine.fuse_with_breakdown(sample_scores)


def seed_pattern_matches(session: Session) -> list[dict[str, Any]]:
    case_data_list = _get_random_case_data(session)
    all_matches = []
    for item in case_data_list[:5]:
        case = item["case"]
        return_record = item["return_record"]
        customer = item["customer"]
        order = item["order"]
        score = item["score"]
        reason_codes = json.loads(score.reason_codes_json) if score.reason_codes_json else []
        matches = match_patterns({
            "return_reason": return_record.return_reason,
            "returned_weight": return_record.returned_weight,
            "expected_weight": order.expected_weight,
            "risk_score": case.risk_score,
            "customer_lifetime_returns": customer.lifetime_returns,
            "customer_lifetime_orders": customer.lifetime_orders,
            "reason_codes": reason_codes,
            "condition_reported": return_record.condition_reported,
        })
        all_matches.append({"case_id": str(case.id), "matches": matches})
    return all_matches


def seed_all_module_data(session: Session) -> dict[str, Any]:
    results: dict[str, Any] = {}

    results["embeddings"] = seed_embeddings(session)

    results["model_registry"] = True
    seed_model_registry()

    results["monitoring"] = True
    seed_monitoring()

    results["alerts"] = True
    seed_alerts(session)

    graph_result = seed_graph_data(session)
    results["graph"] = graph_result

    results["investigations"] = seed_investigations(session)

    results["merchants"] = True
    seed_merchant_configs()

    shap_result = seed_shap_explainability()
    results["shap_explainability"] = shap_result

    fusion_result = seed_fusion_engine()
    results["fusion_engine"] = fusion_result

    pattern_matches = seed_pattern_matches(session)
    results["pattern_matches"] = pattern_matches

    return results
