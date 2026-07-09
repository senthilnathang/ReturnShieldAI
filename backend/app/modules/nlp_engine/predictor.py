from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Optional

from .cleaner import TextCleaner
from .config import nlp_config
from .embeddings import NLPEmbeddingProvider
from .entity_extractor import EntityExtractor
from .evidence_engine import EvidenceEngine
from .fraud_classifier import NLPMultiClassifier
from .intent_classifier import IntentClassifier
from .keyword_detector import KeywordDetector
from .preprocessor import TextPreprocessor
from .sentiment import SentimentAnalyzer
from .similarity_engine import SimilarityEngine
from .toxicity import ToxicityDetector

logger = logging.getLogger(__name__)


class NLPredictor:
    def __init__(
        self,
        classifier: Optional[NLPMultiClassifier] = None,
        intent_clf: Optional[IntentClassifier] = None,
    ):
        self.cleaner = TextCleaner()
        self.preprocessor = TextPreprocessor()
        self.embedding_provider = NLPEmbeddingProvider()
        self.similarity = SimilarityEngine(self.embedding_provider)
        self.entity_extractor = EntityExtractor()
        self.sentiment = SentimentAnalyzer()
        self.toxicity = ToxicityDetector()
        self.keyword_detector = KeywordDetector()
        self.intent_classifier = intent_clf or IntentClassifier()
        self.fraud_classifier = classifier or NLPMultiClassifier()
        self.evidence_engine = EvidenceEngine()

        classifier_path = Path(nlp_config.artifact_root) / "nlp_classifier.pkl"
        if classifier_path.exists():
            self.fraud_classifier = NLPMultiClassifier(str(classifier_path))
        intent_path = Path(nlp_config.artifact_root) / "intent_classifier.pkl"
        if intent_path.exists():
            self.intent_classifier = IntentClassifier(str(intent_path))

    def predict(self, sources: dict[str, str]) -> dict[str, Any]:
        start = time.perf_counter()

        merged_text = self.cleaner.merge_sources(sources)
        if not merged_text.strip():
            return self._empty_result("No text provided for analysis")

        cleaned_sources = self.cleaner.clean_sources(sources)
        preprocessed = self.preprocessor.preprocess_sources(cleaned_sources)
        preprocessed_text = self.preprocessor.preprocess(merged_text)

        embedding = self.embedding_provider.encode_single(merged_text)
        entities = self.entity_extractor.extract(merged_text)
        sentiment = self.sentiment.analyze(merged_text)
        toxicity = self.toxicity.analyze(merged_text)
        keyword_analysis = self.keyword_detector.full_analysis(preprocessed_text)
        intents = self.intent_classifier.predict(preprocessed_text)
        similar_cases = self.similarity.find_similar(
            merged_text, k=nlp_config.similarity_top_k
        )

        keyword_features = {
            "total_matches": sum(
                m.get("total_matches", 0) for m in keyword_analysis.get("keyword_matches", [])
            ),
            "urgency_score": keyword_analysis.get("urgency", {}).get("urgency_score", 0),
            "emotional_score": keyword_analysis.get("emotional_manipulation", {}).get("emotional_score", 0),
            "threat_score": keyword_analysis.get("threats", {}).get("threat_score", 0),
            "contradiction_detected": keyword_analysis.get("contradiction", {}).get("contradiction_detected", False),
            "excessive_certainty": keyword_analysis.get("excessive_certainty", {}).get("excessive_certainty", False),
        }

        fraud_result = self.fraud_classifier.predict(
            embedding, sentiment, intents, keyword_features
        )

        evidence = self.evidence_engine.build(
            text=merged_text[:500],
            fraud_probability=fraud_result["fraud_probability"],
            nlp_score=fraud_result["nlp_score"],
            intents=intents,
            keyword_analysis=keyword_analysis,
            sentiment=sentiment,
            toxicity=toxicity,
            entities=entities,
            similar_cases=similar_cases,
            confidence=fraud_result["confidence"],
        )

        explanation = self.evidence_engine.generate_explanation(evidence)
        latency_ms = int((time.perf_counter() - start) * 1000)

        return {
            "nlp_score": fraud_result["nlp_score"],
            "fraud_probability": fraud_result["fraud_probability"],
            "risk_level": fraud_result["risk_level"],
            "confidence": fraud_result["confidence"],
            "detected_patterns": [e for e in evidence if e.get("severity") in ("high", "medium")],
            "evidence": evidence,
            "explanation": explanation,
            "similar_cases": similar_cases[:5],
            "intents": intents,
            "sentiment": sentiment,
            "toxicity": toxicity,
            "keyword_analysis": keyword_analysis,
            "entities": entities,
            "sources_analyzed": list(sources.keys()),
            "latency_ms": latency_ms,
        }

    def predict_text(self, text: str) -> dict[str, Any]:
        return self.predict({"text": text})

    def _empty_result(self, reason: str) -> dict[str, Any]:
        return {
            "nlp_score": 0,
            "fraud_probability": 0.0,
            "risk_level": "UNKNOWN",
            "confidence": 0.0,
            "detected_patterns": [],
            "evidence": [],
            "explanation": reason,
            "similar_cases": [],
            "intents": {"intents": {}, "primary_intent": None, "primary_score": 0.0},
            "sentiment": {
                "polarity": 0.0, "urgency": 0.0, "frustration": 0.0,
                "aggression": 0.0, "confidence": 0.0, "sentiment_label": "neutral",
            },
            "toxicity": {"toxicity_score": 0.0, "is_toxic": False, "needs_escalation": False},
            "keyword_analysis": {},
            "entities": {},
            "sources_analyzed": [],
            "latency_ms": 0,
        }

    def get_model_info(self) -> dict[str, Any]:
        return {
            "embedding_model": self.embedding_provider.model_name,
            "embedding_dim": self.embedding_provider.dim,
            "embedding_available": self.embedding_provider._available,
            "intent_model_loaded": self.intent_classifier.model is not None,
            "fraud_model_loaded": self.fraud_classifier._active_model is not None,
            "vector_store_size": self.similarity.store.size(),
            "supported_sources": nlp_config.supported_sources,
            "fraud_intents": nlp_config.fraud_intents,
        }
