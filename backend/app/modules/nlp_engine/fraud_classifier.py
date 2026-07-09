from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import joblib
import numpy as np

from .config import nlp_config

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
except ImportError:
    torch = None
    nn = None


class FraudNet(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int = 128, dropout: float = 0.3):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 1),
            nn.Sigmoid(),
        )

    def forward(self, x):
        return self.net(x)


class NLPMultiClassifier:
    def __init__(self, model_path: Optional[str] = None):
        self.models: dict[str, Any] = {}
        self.metadata: dict[str, Any] = {}
        self._active_model = None
        self._feature_dim = 0

        if model_path:
            self._load_bundle(model_path)

    def _load_bundle(self, path: str):
        p = Path(path)
        if not p.exists():
            return
        try:
            bundle = joblib.load(p)
            self._active_model = bundle.get("model")
            self.metadata = bundle.get("metadata", {})
            self._feature_dim = bundle.get("feature_dim", 0)
            logger.info("NLP fraud classifier loaded from %s", path)
        except Exception as e:
            logger.warning("Failed to load NLP classifier: %s", e)

    def predict(
        self,
        embedding: list[float],
        sentiment: dict[str, Any],
        intents: dict[str, Any],
        keyword_features: dict[str, Any],
    ) -> dict[str, Any]:
        features = self._build_features(embedding, sentiment, intents, keyword_features)
        if self._active_model is not None:
            return self._predict_model(features)
        return self._predict_heuristic(features)

    def _build_features(
        self,
        embedding: list[float],
        sentiment: dict[str, Any],
        intents: dict[str, Any],
        keyword_features: dict[str, Any],
    ) -> np.ndarray:
        feat_parts = [embedding]
        feat_parts.append([
            sentiment.get("polarity", 0.0),
            sentiment.get("urgency", 0.0),
            sentiment.get("frustration", 0.0),
            sentiment.get("aggression", 0.0),
            sentiment.get("confidence", 0.0),
        ])
        intent_scores = [v for v in intents.get("intents", {}).values()] if intents else []
        while len(intent_scores) < 10:
            intent_scores.append(0.0)
        feat_parts.append(intent_scores[:10])

        keyword_feats = [
            float(keyword_features.get("total_matches", 0)),
            float(keyword_features.get("urgency_score", 0.0)),
            float(keyword_features.get("emotional_score", 0.0)),
            float(keyword_features.get("threat_score", 0.0)),
            1.0 if keyword_features.get("contradiction_detected", False) else 0.0,
            1.0 if keyword_features.get("excessive_certainty", False) else 0.0,
        ]
        feat_parts.append(keyword_feats)
        combined = np.concatenate([np.array(p, dtype=np.float32).flatten() for p in feat_parts])
        return combined.reshape(1, -1)

    def _predict_model(self, features: np.ndarray) -> dict[str, Any]:
        if self.metadata.get("model_type") == "torch" and torch is not None:
            model = self._active_model
            model.eval()
            with torch.no_grad():
                x = torch.from_numpy(features)
                prob = float(model(x).item())
        elif hasattr(self._active_model, "predict_proba"):
            prob = float(self._active_model.predict_proba(features)[0, 1])
        else:
            prob = float(self._active_model.predict(features)[0])
        score = int(round(prob * 100))
        risk = "HIGH" if prob >= nlp_config.high_risk_threshold else (
            "MEDIUM" if prob >= nlp_config.manual_review_threshold else "LOW"
        )
        return {
            "fraud_probability": round(prob, 4),
            "nlp_score": score,
            "risk_level": risk,
            "confidence": round(abs(prob - 0.5) * 2, 4),
        }

    def _predict_heuristic(self, features: np.ndarray) -> dict[str, Any]:
        f = features.flatten() if features.ndim > 1 else features
        sentiment_part = f[384:389]
        intent_part = f[389:399]
        keyword_part = f[399:406]
        prob = 0.15
        prob += sentiment_part[3] * 0.1 if len(sentiment_part) > 3 else 0.0
        prob += sentiment_part[2] * 0.1 if len(sentiment_part) > 2 else 0.0
        prob += float(keyword_part[0]) * 0.05 if len(keyword_part) > 0 else 0.0
        prob += float(keyword_part[3]) * 0.1 if len(keyword_part) > 3 else 0.0
        prob += float(keyword_part[4]) * 0.15 if len(keyword_part) > 4 else 0.0
        intent_sum = sum(f[389:399])
        prob += intent_sum * 0.03
        prob = max(0.01, min(0.99, prob))
        score = int(round(prob * 100))
        risk = "HIGH" if prob >= nlp_config.high_risk_threshold else (
            "MEDIUM" if prob >= nlp_config.manual_review_threshold else "LOW"
        )
        return {
            "fraud_probability": round(prob, 4),
            "nlp_score": score,
            "risk_level": risk,
            "confidence": round(abs(prob - 0.5) * 2, 4),
        }
