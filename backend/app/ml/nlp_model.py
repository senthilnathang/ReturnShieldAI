from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics.pairwise import cosine_similarity


FRAUD_SCRIPT_PROTOTYPES = [
    "I want a refund immediately or I will open a chargeback",
    "The box was empty and the item was never received",
    "Please refund now or I will dispute this charge",
    "The product was damaged and I need an instant refund",
    "This is the same issue as before please process the refund",
]


@dataclass
class NLPModel:
    vectorizer: TfidfVectorizer = field(default_factory=lambda: TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=2500,
        stop_words="english",
    ))
    classifier: LogisticRegression = field(default_factory=lambda: LogisticRegression(max_iter=1000, class_weight="balanced"))
    prototype_vectorizer: TfidfVectorizer = field(default_factory=lambda: TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=1500,
        stop_words="english",
    ))
    prototype_matrix: Any = None
    fitted: bool = False

    def fit(self, texts: list[str], labels: list[int]):
        X = self.vectorizer.fit_transform(texts)
        self.classifier.fit(X, labels)
        self.prototype_matrix = self.prototype_vectorizer.fit_transform(FRAUD_SCRIPT_PROTOTYPES)
        self.fitted = True

    def score(self, text: str, contextual_flags: dict[str, Any] | None = None) -> tuple[float, list[str], list[str]]:
        result = self.analyze(text, contextual_flags)
        return result["score"], result["flagged_phrases"], result["text_reason_codes"]

    def analyze(self, text: str, contextual_flags: dict[str, Any] | None = None) -> dict[str, Any]:
        contextual_flags = contextual_flags or {}
        if not self.fitted:
            return self._heuristic_analyze(text, contextual_flags)

        X = self.vectorizer.transform([text])
        fraud_probability = float(self.classifier.predict_proba(X)[0][1])
        phrases, codes = self._flagged_phrases(text, contextual_flags)
        similarity_score, similarity_phrase = self._prototype_similarity(text)
        score = min(100.0, round(fraud_probability * 100.0 + similarity_score * 0.25, 2))
        if similarity_phrase:
            phrases.append(similarity_phrase)
            codes.append("SCRIPT_SIMILARITY")
        return {
            "score": score,
            "flagged_phrases": list(dict.fromkeys(phrases))[:6],
            "text_reason_codes": list(dict.fromkeys(codes))[:6],
            "signals": {
                "urgency": round(self._keyword_score(text, ["urgent", "immediately", "asap", "right away"]), 2),
                "manipulation": round(self._keyword_score(text, ["otherwise", "or else", "you must", "need you to"]), 2),
                "repeated_scripts": round(similarity_score, 2),
                "inconsistency": round(self._keyword_score(text, ["changed my mind", "different reason", "not the same", "contradict"]), 2),
                "refund_pressure": round(self._keyword_score(text, ["refund now", "chargeback", "dispute", "replace immediately"]), 2),
            },
            "model_mode": "sentence-transformers-style similarity via TF-IDF fallback",
        }

    def _heuristic_analyze(self, text: str, contextual_flags: dict[str, Any]) -> dict[str, Any]:
        lowered = text.lower()
        score = 0.0
        phrases: list[str] = []
        codes: list[str] = []
        checks = [
            ("empty box", 28, "EMPTY_BOX"),
            ("item not received", 24, "ITEM_NOT_RECEIVED"),
            ("never received", 18, "ITEM_NOT_RECEIVED"),
            ("damaged", 10, "DAMAGED_CLAIM"),
            ("chargeback", 22, "CHARGEBACK_THREAT"),
            ("refund", 8, "REFUND_PRESSURE"),
            ("same issue", 12, "GENERIC_SCRIPT"),
        ]
        for token, points, code in checks:
            if token in lowered:
                score += points
                phrases.append(token)
                codes.append(code)
        if contextual_flags.get("text_generic_script_flag"):
            score += 12
            codes.append("REUSED_SCRIPT")
            phrases.append("reused script-like language")
        similarity_score, similarity_phrase = self._prototype_similarity(text)
        if similarity_phrase:
            phrases.append(similarity_phrase)
            codes.append("SCRIPT_SIMILARITY")
        score += similarity_score * 0.25
        return {
            "score": round(min(score, 100.0), 2),
            "flagged_phrases": list(dict.fromkeys(phrases))[:6],
            "text_reason_codes": list(dict.fromkeys(codes))[:6],
            "signals": {
                "urgency": round(self._keyword_score(text, ["urgent", "immediately", "asap", "right away"]), 2),
                "manipulation": round(self._keyword_score(text, ["otherwise", "or else", "you must", "need you to"]), 2),
                "repeated_scripts": round(similarity_score, 2),
                "inconsistency": round(self._keyword_score(text, ["changed my mind", "different reason", "not the same", "contradict"]), 2),
                "refund_pressure": round(self._keyword_score(text, ["refund now", "chargeback", "dispute", "replace immediately"]), 2),
            },
            "model_mode": "heuristic + tf-idf prototype similarity",
        }

    def _keyword_score(self, text: str, tokens: list[str]) -> float:
        lowered = text.lower()
        score = sum(1 for token in tokens if token in lowered) / max(len(tokens), 1)
        return float(score * 100.0)

    def _prototype_similarity(self, text: str) -> tuple[float, str | None]:
        if self.prototype_matrix is None:
            return 0.0, None
        vector = self.prototype_vectorizer.transform([text])
        similarities = cosine_similarity(vector, self.prototype_matrix)[0]
        best_idx = int(np.argmax(similarities))
        best_score = float(similarities[best_idx]) * 100.0
        if best_score < 20:
            return round(best_score, 2), None
        return round(best_score, 2), FRAUD_SCRIPT_PROTOTYPES[best_idx]

    def _flagged_phrases(self, text: str, contextual_flags: dict[str, Any]) -> tuple[list[str], list[str]]:
        lowered = text.lower()
        phrases: list[str] = []
        codes: list[str] = []
        for token, code in [
            ("empty box", "EMPTY_BOX"),
            ("item not received", "ITEM_NOT_RECEIVED"),
            ("never received", "ITEM_NOT_RECEIVED"),
            ("chargeback", "CHARGEBACK_THREAT"),
            ("damaged", "DAMAGED_CLAIM"),
            ("refund", "REFUND_PRESSURE"),
        ]:
            if token in lowered:
                phrases.append(token)
                codes.append(code)
        if contextual_flags.get("text_generic_script_flag"):
            phrases.append("script-like language")
            codes.append("REUSED_SCRIPT")
        return list(dict.fromkeys(phrases))[:5], list(dict.fromkeys(codes))[:5]
