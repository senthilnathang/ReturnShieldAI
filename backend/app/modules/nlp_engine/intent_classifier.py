from __future__ import annotations

import logging
import re
from typing import Any, Optional

import joblib
import numpy as np

from .config import nlp_config

logger = logging.getLogger(__name__)


class IntentClassifier:
    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.vectorizer = None
        self.label_encoder = None
        self._intents = nlp_config.fraud_intents

        from pathlib import Path
        if model_path:
            p = Path(model_path)
            if p.exists():
                self._load(p)

    def _load(self, path: Path):
        try:
            bundle = joblib.load(path)
            self.model = bundle.get("model")
            self.vectorizer = bundle.get("vectorizer")
            self.label_encoder = bundle.get("label_encoder")
            logger.info("Intent classifier loaded from %s", path)
        except Exception as e:
            logger.warning("Failed to load intent classifier: %s", e)

    def predict(self, text: str, threshold: Optional[float] = None) -> dict[str, Any]:
        threshold = threshold or nlp_config.intent_threshold
        if self.model is not None and self.vectorizer is not None:
            x = self.vectorizer.transform([text])
            if hasattr(self.model, "predict_proba"):
                probs = self.model.predict_proba(x)
                if self.label_encoder and len(probs) == len(self._intents):
                    scores = {}
                    for i, intent in enumerate(self._intents):
                        prob = float(probs[i][0][1]) if probs[i].shape[1] > 1 else float(probs[i][0])
                        if prob >= threshold:
                            scores[intent] = round(prob, 4)
                    return {
                        "intents": scores,
                        "primary_intent": max(scores, key=scores.get) if scores else None,
                        "primary_score": max(scores.values()) if scores else 0.0,
                    }
            labels = self.model.predict(x)[0]
            scores = {}
            for i, intent in enumerate(self._intents):
                prob = float(labels[i]) if hasattr(labels, "__getitem__") else 0.0
                if prob >= threshold:
                    scores[intent] = prob
            return {
                "intents": scores,
                "primary_intent": max(scores, key=scores.get) if scores else None,
                "primary_score": max(scores.values()) if scores else 0.0,
            }
        return self._rule_based(text, threshold)

    def _rule_based(self, text: str, threshold: float) -> dict[str, Any]:
        text_lower = text.lower()
        scores = {}
        for intent, patterns in nlp_config.fraud_keywords.items():
            score = 0.0
            for pattern in patterns:
                if re.search(re.escape(pattern), text_lower):
                    score = max(score, 0.6)
                    break
            if score >= threshold:
                scores[intent] = score
        return {
            "intents": scores,
            "primary_intent": max(scores, key=scores.get) if scores else None,
            "primary_score": max(scores.values()) if scores else 0.0,
        }

    def predict_multi_label(self, text: str) -> dict[str, float]:
        result = self.predict(text, threshold=0.0)
        return result.get("intents", {})
