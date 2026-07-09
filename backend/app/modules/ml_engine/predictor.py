from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import numpy as np

from .config import ml_config
from .feature_store import split_features_target
from .model_registry import load_best_model, load_model

try:
    import torch
except Exception:  # pragma: no cover - optional dependency
    torch = None


@dataclass
class PredictionOutput:
    return_id: str
    model_type: str
    model_version: str
    fraud_probability: float
    ml_score: int
    risk_level: str
    top_features: list[dict[str, Any]]
    latency_ms: int
    cached: bool = False
    fallback_used: bool = False


class MLModelPredictor:
    def __init__(self, model_bundle: dict[str, Any]):
        self.model = model_bundle["model"]
        self.preprocessor = model_bundle["preprocessor"]
        self.metadata = model_bundle["metadata"]
        self.metrics = model_bundle.get("metrics", {})
        self.model_type = self.metadata.get("model_type", "unknown")
        self.version = self.metadata.get("version", "unknown")

    @classmethod
    def load(cls, model_type: str | None = None, version: str | None = None):
        bundle = load_best_model() if model_type is None else load_model(model_type, version or "latest")
        return cls(bundle)

    def _transform(self, frame):
        return self.preprocessor.transform(frame)

    def _predict_probability(self, x):
        if self.metadata.get("model_kind") == "torch" and torch is not None:
            return self.model.predict_proba(x)[:, 1]
        if hasattr(self.model, "predict_proba"):
            return self.model.predict_proba(x)[:, 1]
        if hasattr(self.model, "decision_function"):
            scores = self.model.decision_function(x)
            return 1.0 / (1.0 + np.exp(-scores))
        raise RuntimeError("Model cannot produce probabilities")

    def explain(self, transformed_row, original_row: dict[str, Any], top_k: int = 5) -> list[dict[str, Any]]:
        importance = self.metadata.get("feature_importance", [])
        if importance:
            selected = importance[:top_k]
            return [
                {"feature": item["feature"], "value": original_row.get(item["feature"], None), "impact": "high" if idx == 0 else "medium"}
                for idx, item in enumerate(selected)
            ]

        feature_names = self.metadata.get("preprocessor_features") or []
        if self.model_type == "logistic_regression" and hasattr(self.model, "coef_"):
            weights = np.abs(np.asarray(self.model.coef_)[0])
            order = np.argsort(weights)[::-1][:top_k]
            return [{"feature": feature_names[i] if i < len(feature_names) else f"f{i}", "value": None, "impact": "high" if idx == 0 else "medium"} for idx, i in enumerate(order)]
        return [{"feature": name, "value": original_row.get(name), "impact": "medium"} for name in list(original_row.keys())[:top_k]]

    def predict_frame(self, frame, original_row: dict[str, Any] | None = None) -> dict[str, Any]:
        x = self._transform(frame)
        probs = self._predict_probability(x)
        prob = float(np.asarray(probs)[0])
        score = int(round(prob * 100))
        if prob >= 0.75:
            risk = "HIGH"
        elif prob >= 0.40:
            risk = "MEDIUM"
        else:
            risk = "LOW"
        top_features = self.explain(x[0:1], original_row or frame.iloc[0].to_dict())
        return {
            "model_type": self.model_type,
            "model_version": self.version,
            "fraud_probability": prob,
            "ml_score": score,
            "risk_level": risk,
            "top_features": top_features,
        }
