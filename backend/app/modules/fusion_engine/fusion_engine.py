from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression


DEFAULT_WEIGHTS = {
    "rule_score": 0.25,
    "structured_ml_score": 0.25,
    "nlp_score": 0.20,
    "anomaly_score": 0.15,
    "graph_risk_score": 0.10,
    "customer_risk_score": 0.05,
}


@dataclass
class FusionEngine:
    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    meta_learner: LogisticRegression | None = None
    fitted: bool = False

    def fuse(self, scores: dict[str, float], merchant_config: dict[str, Any] | None = None) -> float:
        weights = self._resolve_weights(merchant_config)
        total = 0.0
        weight_sum = 0.0
        for key, weight in weights.items():
            value = scores.get(key, 0.0)
            total += value * weight
            weight_sum += weight
        if weight_sum > 0:
            total /= weight_sum
        return round(max(0.0, min(100.0, total)), 2)

    def fuse_with_breakdown(self, scores: dict[str, float],
                            merchant_config: dict[str, Any] | None = None) -> dict[str, Any]:
        weights = self._resolve_weights(merchant_config)
        contributions = []
        total = 0.0
        weight_sum = 0.0

        for key, weight in weights.items():
            value = scores.get(key, 0.0)
            contribution = value * weight
            total += contribution
            weight_sum += weight
            if value > 0:
                contributions.append({
                    "name": key,
                    "score": round(value, 2),
                    "weight": weight,
                    "contribution": round(contribution, 2),
                    "share": 0.0,
                })

        final = round(total / max(weight_sum, 0.001), 2) if weight_sum > 0 else 0.0
        for c in contributions:
            c["share"] = round(c["contribution"] / max(total, 0.001), 4) if total > 0 else 0.0

        return {"final_score": final, "contributions": contributions, "weights_used": weights}

    def _resolve_weights(self, merchant_config: dict[str, Any] | None) -> dict[str, float]:
        if merchant_config and "fusion_weights" in merchant_config:
            merged = dict(self.weights)
            merged.update(merchant_config["fusion_weights"])
            return merged
        return dict(self.weights)

    def set_weights(self, weights: dict[str, float]) -> None:
        self.weights.update(weights)

    def fit_meta_learner(self, X: np.ndarray, y: np.ndarray) -> None:
        self.meta_learner = LogisticRegression(random_state=42, max_iter=1000)
        self.meta_learner.fit(X, y)
        self.fitted = True

    def meta_predict(self, scores: list[float]) -> float:
        if not self.fitted or self.meta_learner is None:
            return float(np.mean(scores))
        X = np.array([scores]).reshape(1, -1)
        proba = float(self.meta_learner.predict_proba(X)[0][1])
        return round(max(0.0, min(100.0, proba * 100.0)), 2)


def fuse_scores(rule_score: float, structured_ml_score: float, nlp_score: float,
                anomaly_score: float, graph_risk_score: float = 0.0,
                customer_risk_score: float = 0.0) -> float:
    engine = FusionEngine()
    scores = {
        "rule_score": rule_score,
        "structured_ml_score": structured_ml_score,
        "nlp_score": nlp_score,
        "anomaly_score": anomaly_score,
        "graph_risk_score": graph_risk_score,
        "customer_risk_score": customer_risk_score,
    }
    return engine.fuse(scores)


def decision_from_score(score: float, risk_tolerance: str = "normal") -> tuple[str, str, str]:
    thresholds = {
        "low": (50, 80),
        "normal": (40, 70),
        "high": (30, 60),
    }
    low, high = thresholds.get(risk_tolerance, thresholds["normal"])
    if score < low:
        return "AUTO_APPROVE", "LOW", "Approve automatically; no analyst action needed"
    if score < high:
        return "MANUAL_REVIEW", "MEDIUM", "Queue for analyst review before refund"
    return "HOLD_REFUND_HIGH_RISK", "HIGH", "Hold refund and assign to senior fraud analyst"
