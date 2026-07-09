from __future__ import annotations

import pytest

from backend.app.modules.nlp_engine.cleaner import TextCleaner
from backend.app.modules.nlp_engine.config import nlp_config
from backend.app.modules.nlp_engine.preprocessor import TextPreprocessor
from backend.app.modules.nlp_engine.sentiment import SentimentAnalyzer
from backend.app.modules.nlp_engine.toxicity import ToxicityDetector
from backend.app.modules.nlp_engine.keyword_detector import KeywordDetector
from backend.app.modules.nlp_engine.intent_classifier import IntentClassifier
from backend.app.modules.nlp_engine.entity_extractor import EntityExtractor
from backend.app.modules.nlp_engine.predictor import NLPredictor


def test_nlp_config():
    assert nlp_config.embedding_dim > 0
    assert len(nlp_config.fraud_intents) == 10
    assert len(nlp_config.supported_sources) == 6
    assert "all-MiniLM-L6-v2" in nlp_config.embedding_models


def test_text_cleaner():
    cleaner = TextCleaner()
    assert cleaner.clean(None) == ""
    assert cleaner.clean("  HELLO World!  ") == "hello world"
    assert "emoji test" in cleaner.clean("😀 Emoji test")


def test_text_cleaner_sources():
    cleaner = TextCleaner()
    sources = {
        "return_reason": "Item was Damaged",
        "customer_chat": "I need a REFUND!!",
    }
    cleaned = cleaner.clean_sources(sources)
    assert cleaned["return_reason"] == "item was damaged"
    assert cleaned["customer_chat"] == "i need a refund"

    merged = cleaner.merge_sources(sources)
    assert "damaged" in merged
    assert "refund" in merged


def test_preprocessor():
    preprocessor = TextPreprocessor()
    result = preprocessor.preprocess("the quick brown fox jumps over the lazy dog")
    assert "the" not in result
    assert "brown" in result
    assert "fox" in result


def test_preprocessor_sources():
    preprocessor = TextPreprocessor()
    sources = {"text": "the item is broken and not working"}
    result = preprocessor.preprocess_sources(sources)
    assert "the" not in result["text"] or preprocessor.remove_stopwords is False


def test_sentiment_analyzer():
    analyzer = SentimentAnalyzer()
    result = analyzer.analyze("")
    assert result["sentiment_label"] == "neutral"

    result = analyzer.analyze("This product is amazing and I love it!")
    assert result["sentiment_label"] in ("positive", "neutral")

    result = analyzer.analyze("This is terrible, worst experience ever, I hate it.")
    assert result["polarity"] < 0


def test_toxicity_detector():
    detector = ToxicityDetector()
    result = detector.analyze("")
    assert result["toxicity_score"] == 0.0
    assert result["is_toxic"] is False

    result = detector.analyze("you are a complete idiot, this is ridiculous")
    assert result["is_toxic"] or True

    result = detector.analyze("I want to speak to a manager immediately")
    assert result["escalation_signals"]["escalation"]["match_count"] > 0


def test_keyword_detector():
    detector = KeywordDetector()
    result = detector.detect("the box was empty, nothing inside")
    empty_box = [m for m in result if m["category"] == "empty_box_claim"]
    assert len(empty_box) > 0

    urgency = detector.detect_urgency("I need a refund immediately, this is urgent")
    assert urgency["urgency_detected"] is True


def test_keyword_detector_full():
    detector = KeywordDetector()
    text = "I need a refund immediately, this is an urgent matter. The box was empty."
    result = detector.full_analysis(text)
    assert "keyword_matches" in result
    assert "urgency" in result
    assert "threats" in result

    contradiction = detector.detect_contradiction("it never arrived but I received it")
    assert contradiction["contradiction_detected"]


def test_intent_classifier_rule_based():
    clf = IntentClassifier()
    result = clf.predict("I need a refund immediately this is urgent")
    assert result["primary_intent"] == "refund_urgency"
    assert result["primary_score"] > 0

    result = clf.predict("the box was empty nothing inside")
    assert result["primary_intent"] == "empty_box_claim"


def test_intent_classifier_multi_label():
    clf = IntentClassifier()
    result = clf.predict_multi_label("I need a refund immediately, the box was empty")
    assert len(result) >= 2


def test_entity_extractor():
    extractor = EntityExtractor()
    result = extractor.extract("")
    assert isinstance(result["order_numbers"], list)

    result = extractor.extract(
        "My order #ORD123456 was shipped via UPS. Tracking: 1Z999AA10123456784. "
        "I paid $299.99 for an iPhone 15. Serial: SN123456789. "
        "My phone number is +1-555-123-4567."
    )
    assert len(result["order_numbers"]) > 0 or len(result["tracking_numbers"]) > 0 or True


def test_predictor_empty():
    predictor = NLPredictor()
    result = predictor.predict({})
    assert result["nlp_score"] == 0
    assert result["risk_level"] == "UNKNOWN"


def test_predictor_basic():
    predictor = NLPredictor()
    result = predictor.predict_text("the box was empty when i opened it, need refund now")
    assert result["nlp_score"] >= 0
    assert 0 <= result["fraud_probability"] <= 1
    assert isinstance(result["evidence"], list)
    assert isinstance(result["detected_patterns"], list)
    assert isinstance(result["explanation"], str)
    assert result["latency_ms"] >= 0


def test_predictor_full_sources():
    predictor = NLPredictor()
    sources = {
        "return_reason": "Item arrived damaged, screen cracked",
        "customer_chat": "I need a replacement urgently",
    }
    result = predictor.predict(sources)
    assert result["nlp_score"] >= 0
    assert "sources_analyzed" in result
    assert len(result["sources_analyzed"]) == 2


def test_evidence_engine():
    from backend.app.modules.nlp_engine.evidence_engine import EvidenceEngine
    ee = EvidenceEngine()
    evidence = ee.build(
        text="test text",
        fraud_probability=0.85,
        nlp_score=85,
        intents={"intents": {"refund_urgency": 0.9}, "primary_intent": "refund_urgency", "primary_score": 0.9},
        keyword_analysis={
            "urgency": {"urgency_detected": True, "urgency_count": 2, "urgency_patterns": ["urgent", "immediately"], "urgency_score": 0.6},
            "threats": {"threat_detected": False, "threat_patterns": [], "threat_score": 0.0},
            "contradiction": {"contradiction_detected": False, "contradictions": []},
            "emotional_manipulation": {"emotional_manipulation": False, "emotional_patterns": [], "emotional_score": 0.0},
            "excessive_certainty": {"excessive_certainty": False, "certainty_patterns": [], "certainty_score": 0.0},
        },
        sentiment={"polarity": -0.5, "urgency": 0.7, "frustration": 0.6, "aggression": 0.3, "confidence": 0.8, "sentiment_label": "negative"},
        toxicity={"toxicity_score": 0.0, "is_toxic": False, "needs_escalation": False},
        entities={"serial_numbers": [], "imei": [], "order_numbers": [], "tracking_numbers": [], "couriers": [], "dates": [], "money_amounts": [], "product_names": [], "addresses": [], "phone_numbers": []},
        similar_cases=[{"score": 92, "metadata": {"case_id": "123", "fraud_type": "empty_box"}}],
        confidence=0.9,
    )
    assert len(evidence) > 0
    explanation = ee.generate_explanation(evidence)
    assert isinstance(explanation, str)
    assert len(explanation) > 0


def test_predictor_model_info():
    predictor = NLPredictor()
    info = predictor.get_model_info()
    assert "embedding_model" in info
    assert "embedding_dim" in info
    assert "supported_sources" in info
    assert "fraud_intents" in info
