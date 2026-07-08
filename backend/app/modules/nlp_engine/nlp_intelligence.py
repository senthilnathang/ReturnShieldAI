from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics.pairwise import cosine_similarity

from backend.app.ml.nlp_model import FRAUD_SCRIPT_PROTOTYPES
from backend.app.modules.vector_engine.embedding_service import EmbeddingService


FRAUD_SIGNAL_KEYWORDS = {
    "urgency": ["urgent", "immediately", "asap", "right away", "emergency", "today"],
    "manipulation": ["otherwise", "or else", "you must", "need you to", "if you don't"],
    "refund_pressure": ["refund now", "chargeback", "dispute", "replace immediately", "money back"],
    "empty_box": ["empty box", "box was empty", "nothing inside", "missing item", "bubble wrap"],
    "item_not_received": ["item not received", "never received", "did not receive", "not delivered"],
    "damaged_claim": ["damaged", "broken", "defective", "arrived damaged", "cracked"],
    "inconsistency": ["changed my mind", "different reason", "not the same", "contradict", "actually"],
    "threat": ["lawyer", "attorney", "sue", "legal action", "complaint", "better business bureau"],
    "chargeback_threat": ["chargeback", "credit card dispute", "refund or else", "dispute this charge"],
}


@dataclass
class NLPIntelligenceEngine:
    vectorizer: TfidfVectorizer = field(default_factory=lambda: TfidfVectorizer(
        ngram_range=(1, 3),
        max_features=3000,
        stop_words="english",
        sublinear_tf=True,
    ))
    classifier: LogisticRegression = field(default_factory=lambda: LogisticRegression(
        max_iter=1000, class_weight="balanced", C=1.0, random_state=42
    ))
    prototype_vectorizer: TfidfVectorizer = field(default_factory=lambda: TfidfVectorizer(
        ngram_range=(1, 3), max_features=2000, stop_words="english", sublinear_tf=True
    ))
    prototype_matrix: Any = None
    fitted: bool = False
    embedding_service: EmbeddingService | None = None

    def fit(self, texts: list[str], labels: list[int]):
        X = self.vectorizer.fit_transform(texts)
        self.classifier.fit(X, labels)
        self.prototype_matrix = self.prototype_vectorizer.fit_transform(FRAUD_SCRIPT_PROTOTYPES)
        self.fitted = True

    def _compute_signal_scores(self, text: str) -> dict[str, float]:
        lowered = text.lower()
        scores = {}
        for signal, keywords in FRAUD_SIGNAL_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in lowered)
            scores[signal] = round((matches / max(len(keywords), 1)) * 100.0, 2)
        return scores

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

    def _semantic_similarity_search(self, text: str) -> dict[str, Any]:
        if self.embedding_service is None:
            return {"similar_cases": [], "top_similarity": 0.0, "common_fraud_type": None}
        results = self.embedding_service.search_similar(text, k=5)
        top_score = results[0]["score"] if results else 0.0
        fraud_types = [r["metadata"].get("decision", "") for r in results if r["score"] > 50]
        common = max(set(fraud_types), key=fraud_types.count) if fraud_types else None
        return {
            "similar_cases": results[:3],
            "top_similarity": top_score,
            "common_fraud_type": common,
        }

    def analyze(self, text: str, contextual_flags: dict[str, Any] | None = None) -> dict[str, Any]:
        contextual_flags = contextual_flags or {}
        signals = self._compute_signal_scores(text)
        similarity_score, similarity_phrase = self._prototype_similarity(text)
        semantic = self._semantic_similarity_search(text)

        if self.fitted:
            X = self.vectorizer.transform([text])
            fraud_probability = float(self.classifier.predict_proba(X)[0][1])
            base_score = fraud_probability * 100.0
        else:
            base_score = self._heuristic_score(text, contextual_flags)

        score = min(100.0, round(base_score + similarity_score * 0.2 + semantic["top_similarity"] * 0.15, 2))

        flagged_phrases = self._extract_flagged_phrases(text, contextual_flags)
        if similarity_phrase:
            flagged_phrases.append(similarity_phrase)

        text_reason_codes = self._extract_reason_codes(text, contextual_flags)
        if similarity_phrase:
            text_reason_codes.append("SCRIPT_SIMILARITY")
        if semantic["top_similarity"] > 50:
            text_reason_codes.append("SEMANTIC_FRAUD_MATCH")

        return {
            "score": score,
            "flagged_phrases": list(dict.fromkeys(flagged_phrases))[:8],
            "text_reason_codes": list(dict.fromkeys(text_reason_codes))[:8],
            "signals": signals,
            "prototype_similarity": similarity_score,
            "semantic_search": semantic,
            "model_mode": "sentence-transformers + tf-idf ensemble",
        }

    def _heuristic_score(self, text: str, contextual_flags: dict[str, Any]) -> float:
        lowered = text.lower()
        score = 0.0
        checks = [
            ("empty box", 28), ("item not received", 24), ("never received", 18),
            ("damaged", 10), ("chargeback", 22), ("refund", 8), ("same issue", 12),
        ]
        for token, points in checks:
            if token in lowered:
                score += points
        if contextual_flags.get("text_generic_script_flag"):
            score += 12
        return min(score, 100.0)

    def _extract_flagged_phrases(self, text: str, contextual_flags: dict[str, Any]) -> list[str]:
        lowered = text.lower()
        phrases = []
        for phrase in ["empty box", "item not received", "never received", "chargeback", "damaged", "refund", "lawyer", "dispute", "same issue"]:
            if phrase in lowered:
                phrases.append(phrase)
        if contextual_flags.get("text_generic_script_flag"):
            phrases.append("script-like language")
        return phrases

    def _extract_reason_codes(self, text: str, contextual_flags: dict[str, Any]) -> list[str]:
        lowered = text.lower()
        codes = []
        mapping = [
            ("empty box", "EMPTY_BOX"), ("item not received", "ITEM_NOT_RECEIVED"),
            ("never received", "ITEM_NOT_RECEIVED"), ("chargeback", "CHARGEBACK_THREAT"),
            ("damaged", "DAMAGED_CLAIM"), ("refund", "REFUND_PRESSURE"),
        ]
        for token, code in mapping:
            if token in lowered:
                codes.append(code)
        if contextual_flags.get("text_generic_script_flag"):
            codes.append("REUSED_SCRIPT")
        return codes
