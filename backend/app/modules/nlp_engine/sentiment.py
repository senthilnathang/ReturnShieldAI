from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _vader = SentimentIntensityAnalyzer()
except ImportError:
    _vader = None
    logger.warning("vaderSentiment not installed; using simple lexicon fallback")


class SentimentAnalyzer:
    def __init__(self):
        self._vader = _vader

    def analyze(self, text: str) -> dict[str, Any]:
        if not text.strip():
            return self._empty()
        if self._vader:
            return self._analyze_vader(text)
        return self._analyze_fallback(text)

    def _empty(self) -> dict[str, Any]:
        return {
            "polarity": 0.0,
            "urgency": 0.0,
            "frustration": 0.0,
            "aggression": 0.0,
            "confidence": 0.0,
            "sentiment_label": "neutral",
        }

    def _analyze_vader(self, text: str) -> dict[str, Any]:
        scores = self._vader.polarity_scores(text)
        compound = scores["compound"]
        pos = scores["pos"]
        neg = scores["neg"]

        if compound >= 0.05:
            label = "positive"
        elif compound <= -0.05:
            label = "negative"
        else:
            label = "neutral"

        urgency = self._compute_urgency(text)
        frustration = self._compute_frustration(text, neg)
        aggression = self._compute_aggression(text)
        confidence = round(abs(compound), 4)

        return {
            "polarity": round(compound, 4),
            "urgency": round(urgency, 4),
            "frustration": round(frustration, 4),
            "aggression": round(aggression, 4),
            "confidence": confidence,
            "sentiment_label": label,
            "vader_scores": scores,
        }

    def _analyze_fallback(self, text: str) -> dict[str, Any]:
        text_lower = text.lower()
        positive_words = {"good", "great", "excellent", "happy", "satisfied", "thank",
                          "perfect", "love", "wonderful", "amazing", "pleased", "fine"}
        negative_words = {"bad", "terrible", "awful", "horrible", "worst", "hate",
                          "angry", "frustrated", "disappointed", "poor", "upset",
                          "useless", "broken", "damaged", "defective", "waste"}

        words = text_lower.split()
        pos_count = sum(1 for w in words if w in positive_words)
        neg_count = sum(1 for w in words if w in negative_words)
        total = len(words) or 1
        polarity = (pos_count - neg_count) / total
        return {
            "polarity": round(polarity, 4),
            "urgency": round(self._compute_urgency(text), 4),
            "frustration": round(min(1.0, neg_count * 0.15), 4),
            "aggression": round(self._compute_aggression(text), 4),
            "confidence": round(min(1.0, (pos_count + neg_count) / max(total * 0.1, 1)), 4),
            "sentiment_label": "positive" if polarity > 0.05 else "negative" if polarity < -0.05 else "neutral",
        }

    def _compute_urgency(self, text: str) -> float:
        urgency_words = [
            "urgent", "immediately", "asap", "right now", "today", "hurry",
            "emergency", "fast", "quick", "pressing", "critical", "deadline",
            "as soon as possible", "no later than", "priority",
        ]
        text_lower = text.lower()
        count = sum(1 for w in urgency_words if w in text_lower)
        return min(1.0, count * 0.15)

    def _compute_frustration(self, text: str, neg_score: float) -> float:
        frustration_words = [
            "frustrated", "frustrating", "unacceptable", "ridiculous",
            "absurd", "outrageous", "pathetic", "useless", "hopeless",
            "sick of", "tired of", "fed up", "disgusted", "annoyed",
            "irritated", "aggravated", "exasperated",
        ]
        text_lower = text.lower()
        count = sum(1 for w in frustration_words if w in text_lower)
        return min(1.0, neg_score * 0.7 + count * 0.12)

    def _compute_aggression(self, text: str) -> float:
        aggression_words = [
            "sue", "lawsuit", "lawyer", "attorney", "legal action",
            "complaint", "chargeback", "dispute", "manager now",
            "supervisor", "escalate", "demand", "demanding",
            "refund now", "give me", "you must", "you better",
        ]
        text_lower = text.lower()
        count = sum(1 for w in aggression_words if w in text_lower)
        return min(1.0, count * 0.12)
