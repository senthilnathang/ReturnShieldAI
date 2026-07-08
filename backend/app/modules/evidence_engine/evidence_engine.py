from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class EvidenceItem:
    category: str
    label: str
    detail: str
    confidence: float
    source: str
    score: float
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class EvidenceEngine:
    def __init__(self):
        self.evidence: list[EvidenceItem] = []

    def build_evidence(self, score_breakdown: dict[str, float], reason_codes: list[str],
                       advanced_signals: dict[str, Any], customer_risk_score: float,
                       flagged_phrases: list[str] | None = None) -> list[dict[str, Any]]:
        self.evidence.clear()
        self._add_behavior_evidence(score_breakdown, advanced_signals)
        self._add_graph_evidence(advanced_signals)
        self._add_nlp_evidence(score_breakdown, flagged_phrases, advanced_signals)
        self._add_ml_evidence(score_breakdown, advanced_signals)
        self._add_rule_evidence(reason_codes, score_breakdown)
        self._add_customer_risk_evidence(customer_risk_score)
        return [self._to_dict(item) for item in self.evidence]

    def _add_behavior_evidence(self, scores: dict[str, float], signals: dict[str, Any]) -> None:
        structured = scores.get("structured_ml_score", 0)
        family = signals.get("behavioral_ml", {}).get("family_scores", {})
        if structured >= 30:
            self.evidence.append(EvidenceItem(
                category="behavior",
                label="High behavioral risk score",
                detail=f"Structured ML score {structured:.1f} indicates elevated fraud probability.",
                confidence=min(95.0, structured),
                source="structured_ml_ensemble",
                score=structured,
            ))
        for name, val in family.items():
            if val >= 20:
                self.evidence.append(EvidenceItem(
                    category="behavior",
                    label=f"{name} flagged",
                    detail=f"{name} model returned score {val:.1f}.",
                    confidence=min(90.0, val),
                    source=f"structured_ml.{name}",
                    score=val,
                ))

    def _add_graph_evidence(self, signals: dict[str, Any]) -> None:
        graph = signals.get("graph_fraud", {})
        if graph.get("ring_risk_score", 0) >= 30:
            self.evidence.append(EvidenceItem(
                category="graph",
                label="Fraud ring detected",
                detail=graph.get("summary", ""),
                confidence=min(95.0, float(graph.get("ring_risk_score", 0))),
                source="fraud_graph",
                score=float(graph.get("ring_risk_score", 0)),
            ))
        for signal in graph.get("signals", []):
            self.evidence.append(EvidenceItem(
                category="graph",
                label=signal,
                detail=f"Graph signal: {signal}",
                confidence=75.0,
                source="fraud_graph",
                score=float(graph.get("ring_risk_score", 0)),
            ))

    def _add_nlp_evidence(self, scores: dict[str, float], phrases: list[str] | None,
                          signals: dict[str, Any]) -> None:
        nlp_score = scores.get("nlp_score", 0)
        if nlp_score >= 20:
            self.evidence.append(EvidenceItem(
                category="nlp",
                label="Fraud language detected",
                detail=f"NLP score {nlp_score:.1f}: text analysis indicates fraud pressure.",
                confidence=min(90.0, nlp_score),
                source="nlp_engine",
                score=nlp_score,
            ))
        if phrases:
            for phrase in phrases[:3]:
                self.evidence.append(EvidenceItem(
                    category="nlp",
                    label=f"Flagged phrase: {phrase}",
                    detail=f"Return text contains keyword '{phrase}' associated with fraud.",
                    confidence=80.0,
                    source="nlp_engine",
                    score=nlp_score,
                ))

    def _add_ml_evidence(self, scores: dict[str, float], signals: dict[str, Any]) -> None:
        anomaly = scores.get("anomaly_score", 0)
        if anomaly >= 20:
            self.evidence.append(EvidenceItem(
                category="ml",
                label="Anomalous transaction",
                detail=f"Anomaly detection score {anomaly:.1f}: transaction is an outlier.",
                confidence=min(85.0, anomaly),
                source="anomaly_detector",
                score=anomaly,
            ))

    def _add_rule_evidence(self, reason_codes: list[str], scores: dict[str, float]) -> None:
        rule_score = scores.get("rule_score", 0)
        for reason in reason_codes:
            self.evidence.append(EvidenceItem(
                category="rules",
                label=f"Rule fired: {reason}",
                detail=reason,
                confidence=100.0,
                source="rule_engine",
                score=rule_score,
            ))

    def _add_customer_risk_evidence(self, customer_risk_score: float) -> None:
        if customer_risk_score >= 30:
            self.evidence.append(EvidenceItem(
                category="behavior",
                label="Elevated customer risk history",
                detail=f"Customer risk score {customer_risk_score:.1f} from return velocity, address/device reuse, and prior fraud.",
                confidence=min(90.0, customer_risk_score),
                source="customer_risk_profile",
                score=customer_risk_score,
            ))

    def _to_dict(self, item: EvidenceItem) -> dict[str, Any]:
        return {
            "category": item.category,
            "label": item.label,
            "detail": item.detail,
            "confidence": item.confidence,
            "source": item.source,
            "score": item.score,
            "timestamp": item.timestamp,
        }
