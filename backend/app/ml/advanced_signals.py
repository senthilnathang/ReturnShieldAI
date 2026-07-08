from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select

from backend.app.ml.graph_features import build_fraud_graph, extract_graph_features
from backend.app.models import AnalystFeedback, Customer, FraudScore, Order, ReturnCase, ReturnRecord


@dataclass
class AdvancedSignalSet:
    behavioral_ml: dict[str, Any]
    nlp_detection: dict[str, Any]
    image_verification: dict[str, Any]
    graph_fraud: dict[str, Any]
    llm_investigator: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "behavioral_ml": self.behavioral_ml,
            "nlp_detection": self.nlp_detection,
            "image_verification": self.image_verification,
            "graph_fraud": self.graph_fraud,
            "llm_investigator": self.llm_investigator,
        }


def _score_from_count(count: int, scale: float = 12.0, cap: float = 100.0) -> float:
    return round(min(cap, float(count) * scale), 2)


def build_graph_fraud(session: Session, customer: Customer, order: Order, return_record: ReturnRecord) -> dict[str, Any]:
    customers = session.exec(select(Customer)).all()
    orders = session.exec(select(Order)).all()
    returns = session.exec(select(ReturnRecord)).all()
    bundle = build_fraud_graph(customers, orders, returns)

    confirmed_fraud_customers = {
        customer_id
        for customer_id in session.exec(
            select(ReturnRecord.customer_id)
            .join(FraudScore, FraudScore.return_id == ReturnRecord.id)
            .where(FraudScore.final_score >= 70)
        ).all()
    }
    confirmed_fraud_customers.update(
        customer_id
        for customer_id in session.exec(
            select(ReturnRecord.customer_id)
            .join(ReturnCase, ReturnCase.return_id == ReturnRecord.id)
            .join(AnalystFeedback, AnalystFeedback.case_id == ReturnCase.id)
            .where(AnalystFeedback.confirmed_label == "confirmed_fraud")
        ).all()
    )
    bundle.confirmed_fraud_customers = confirmed_fraud_customers

    features = extract_graph_features(bundle, customer.id, return_record.id)
    return {
        "score": float(features["ring_risk_score"]),
        "ring_size": features["component_size"],
        "connected_customers_count": features["connected_customers_count"],
        "shared_address_accounts": features["shared_address_count"],
        "shared_device_accounts": features["shared_device_count"],
        "shared_payment_orders": features["shared_payment_count"],
        "shared_refund_account_count": features["shared_refund_account_count"],
        "shared_phone_accounts": features["shared_phone_count"],
        "text_similarity_cluster_size": features["text_similarity_cluster_size"],
        "fraud_neighbor_count": features["fraud_neighbor_count"],
        "ring_risk_score": features["ring_risk_score"],
        "shortest_path_to_fraud": features["shortest_path_to_fraud"],
        "component_size": features["component_size"],
        "high_risk_neighbor_ratio": features["high_risk_neighbor_ratio"],
        "same_sku_return_cluster_count": features["same_sku_return_cluster_count"],
        "same_pickup_location_count": features["same_pickup_location_count"],
        "return_velocity_in_component": features["return_velocity_in_component"],
        "signals": features["signals"],
        "reason_codes": features["reason_codes"],
        "summary": features["summary"],
    }

def build_image_verification(payload: Any, order: Order, customer: Customer, return_record: ReturnRecord) -> dict[str, Any]:
    delivery_photo_url = getattr(payload.return_data, "delivery_photo_url", "") or ""
    return_photo_url = getattr(payload.return_data, "return_photo_url", "") or ""
    shipping_label_text = getattr(payload.return_data, "shipping_label_text", "") or ""
    ocr_text = getattr(payload.return_data, "ocr_text", "") or ""

    if not any([delivery_photo_url, return_photo_url, shipping_label_text, ocr_text]):
        return {
            "score": 0.0,
            "summary": "No delivery or return images were supplied, so image verification could not be run.",
            "signals": [],
            "reason_codes": ["No image evidence supplied"],
            "ocr_match": 0.0,
            "photo_similarity": 0.0,
        }

    score = 0.0
    signals: list[str] = []
    reason_codes: list[str] = []
    expected_tokens = [customer.address.lower().split()[0], order.sku.lower(), order.product_name.lower().split()[0]]
    ocr_lower = ocr_text.lower()
    shipping_lower = shipping_label_text.lower()

    if ocr_text:
        matches = sum(1 for token in expected_tokens if token and token in ocr_lower)
        ocr_match = round((matches / max(len(expected_tokens), 1)) * 100.0, 2)
        if ocr_match < 50:
            score += 28
            signals.append("OCR label mismatch")
            reason_codes.append("OCR label mismatch")
        else:
            score += max(0.0, 20.0 - (ocr_match - 50.0) * 0.2)
            signals.append("OCR label match")
    else:
        ocr_match = 0.0
        score += 10
        reason_codes.append("Missing OCR text")

    if shipping_label_text and ocr_text and shipping_lower != ocr_lower:
        score += 12
        signals.append("Shipping label text differs from OCR")
        reason_codes.append("Shipping label mismatch")

    if delivery_photo_url and return_photo_url and delivery_photo_url == return_photo_url:
        score += 20
        signals.append("Same image reused")
        reason_codes.append("Reused delivery and return photo")

    if "empty box" in ocr_lower or "empty-box" in ocr_lower:
        score += 18
        signals.append("Empty-box claim in image evidence")
        reason_codes.append("Empty-box photo claim")

    if "damaged" in ocr_lower:
        score += 10
        signals.append("Damage claim in OCR")
        reason_codes.append("Damaged-item OCR claim")

    if return_record.condition_reported in {"empty_box", "damaged"}:
        score += 8
        signals.append("Condition report supports fraud pattern")
        reason_codes.append("Condition claim aligned with return text")

    return {
        "score": round(min(100.0, score), 2),
        "summary": "Image evidence supports the fraud hypothesis." if score >= 25 else "Image evidence is inconclusive or weak.",
        "signals": signals[:6],
        "reason_codes": list(dict.fromkeys(reason_codes))[:6],
        "ocr_match": ocr_match,
        "photo_similarity": 100.0 if delivery_photo_url and delivery_photo_url == return_photo_url else 0.0,
    }


def build_llm_investigation(
    *,
    decision: str,
    explanation: str,
    reason_codes: list[str],
    graph_fraud: dict[str, Any],
    image_verification: dict[str, Any],
    nlp_detection: dict[str, Any],
    behavioral_ml: dict[str, Any],
) -> dict[str, Any]:
    evidence = [code for code in reason_codes[:4]]
    if graph_fraud.get("reason_codes"):
        evidence.extend(graph_fraud["reason_codes"][:2])
    if image_verification.get("reason_codes"):
        evidence.extend(image_verification["reason_codes"][:2])

    evidence = list(dict.fromkeys(evidence))[:6]
    recommendation = {
        "AUTO_APPROVE": "Approve refund and close the case.",
        "MANUAL_REVIEW": "Review the evidence before refund release.",
        "HOLD_REFUND_HIGH_RISK": "Hold the refund and escalate to fraud operations.",
    }.get(decision, "Review the return manually.")

    summary = (
        f"{explanation} The strongest cluster is {graph_fraud.get('summary', '').lower()}"
        if graph_fraud.get("score", 0) >= 30
        else explanation
    )
    summary = f"{summary} NLP flags indicate {', '.join((nlp_detection.get('flagged_phrases') or [])[:2])}." if nlp_detection.get("flagged_phrases") else summary

    return {
        "summary": summary,
        "recommendation": recommendation,
        "evidence": evidence,
        "analyst_notes": [
            "Verify package weight against original shipment label.",
            "Check for repeated return behavior across linked accounts.",
            "Review OCR and image consistency before releasing the refund.",
        ],
        "behavioral_ml_readout": behavioral_ml,
    }


def build_advanced_signals(session: Session, payload: Any, customer: Customer, order: Order, return_record: ReturnRecord, *, explanation: str, decision: str, reason_codes: list[str], structured: dict[str, Any], nlp: dict[str, Any]) -> dict[str, Any]:
    graph_fraud = build_graph_fraud(session, customer, order, return_record)
    image_verification = build_image_verification(payload, order, customer, return_record)
    behavioral_ml = {
        "summary": "Behavioral ML blends multiple tree models over customer, order, and return activity.",
        "family_scores": structured.get("family_scores", {}),
        "reason_codes": structured.get("reasons", []),
        "models": ["RandomForest", "LightGBM-style", "XGBoost-style"],
    }
    llm_investigator = build_llm_investigation(
        decision=decision,
        explanation=explanation,
        reason_codes=reason_codes,
        graph_fraud=graph_fraud,
        image_verification=image_verification,
        nlp_detection=nlp,
        behavioral_ml=behavioral_ml,
    )
    return {
        "behavioral_ml": behavioral_ml,
        "nlp_detection": {
            "summary": "Semantic fraud detection over return reason, chat transcript, and email text.",
            "score": nlp.get("score", 0.0),
            "signals": nlp.get("signals", {}),
            "flagged_phrases": nlp.get("flagged_phrases", []),
            "text_reason_codes": nlp.get("text_reason_codes", []),
            "model_mode": nlp.get("model_mode", "heuristic"),
        },
        "image_verification": image_verification,
        "graph_fraud": graph_fraud,
        "llm_investigator": llm_investigator,
    }
