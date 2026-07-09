from __future__ import annotations

import re
from typing import Any, Optional

from .config import nlp_config


class KeywordDetector:
    def __init__(self, custom_patterns: Optional[dict[str, list[str]]] = None):
        self.patterns = custom_patterns or nlp_config.fraud_keywords

    def detect(self, text: str) -> list[dict[str, Any]]:
        if not text:
            return []
        text_lower = text.lower()
        matches = []
        for category, keywords in self.patterns.items():
            category_matches = []
            for keyword in keywords:
                count = len(re.findall(re.escape(keyword), text_lower))
                if count > 0:
                    category_matches.append({
                        "keyword": keyword,
                        "count": count,
                        "positions": self._find_positions(text_lower, keyword),
                    })
            if category_matches:
                matches.append({
                    "category": category,
                    "matches": category_matches,
                    "total_matches": sum(m["count"] for m in category_matches),
                })
        return matches

    def _find_positions(self, text: str, keyword: str) -> list[int]:
        positions = []
        start = 0
        while True:
            idx = text.find(keyword, start)
            if idx == -1:
                break
            positions.append(idx)
            start = idx + 1
        return positions

    def detect_urgency(self, text: str) -> dict[str, Any]:
        urgency_patterns = [
            "urgent", "immediately", "asap", "right now", "today",
            "hurry", "fast", "quick", "emergency", "priority",
        ]
        text_lower = text.lower()
        matches = [p for p in urgency_patterns if p in text_lower]
        return {
            "urgency_detected": len(matches) > 0,
            "urgency_patterns": matches,
            "urgency_count": len(matches),
            "urgency_score": min(1.0, len(matches) * 0.2),
        }

    def detect_emotional_manipulation(self, text: str) -> dict[str, Any]:
        patterns = [
            "i can't believe", "this is ridiculous", "unacceptable",
            "worst experience", "terrible service", "disgusting",
            "shocking", "appalling", "nightmare", "horrible",
            "crying", "tears", "depressed", "anxious", "stress",
            "sick of", "fed up", "outrageous",
        ]
        text_lower = text.lower()
        matches = [p for p in patterns if p in text_lower]
        return {
            "emotional_manipulation": len(matches) > 0,
            "emotional_patterns": matches,
            "emotional_score": min(1.0, len(matches) * 0.15),
        }

    def detect_contradiction(self, text: str) -> dict[str, Any]:
        contradiction_pairs = [
            (r"\bnever arrived\b", r"\breceived\b"),
            (r"\bempty box\b", r"\binside\b"),
            (r"\bnot working\b", r"\bworks fine\b"),
            (r"\bdidn't receive\b", r"\bgot it\b"),
            (r"\bbroken\b", r"\bperfect condition\b"),
        ]
        text_lower = text.lower()
        contradictions = []
        for a, b in contradiction_pairs:
            has_a = bool(re.search(a, text_lower))
            has_b = bool(re.search(b, text_lower))
            if has_a and has_b:
                contradictions.append({"pattern_a": a, "pattern_b": b})
        return {
            "contradiction_detected": len(contradictions) > 0,
            "contradictions": contradictions,
        }

    def detect_excessive_certainty(self, text: str) -> dict[str, Any]:
        patterns = [
            r"\babsolutely sure\b", r"\b100%\b", r"\bpositive\b",
            r"\bdefinitely\b", r"\bwithout a doubt\b", r"\bguaranteed\b",
            r"\bcertain\b", r"\bconvinced\b", r"\bno question\b",
            r"\bbeyond any doubt\b",
        ]
        text_lower = text.lower()
        matches = [p for p in patterns if re.search(p, text_lower)]
        return {
            "excessive_certainty": len(matches) > 0,
            "certainty_patterns": matches,
            "certainty_score": min(1.0, len(matches) * 0.2),
        }

    def detect_threats(self, text: str) -> dict[str, Any]:
        threat_patterns = [
            "chargeback", "dispute", "lawyer", "legal action", "sue",
            "attorney", "complaint", "better business bureau", "bbb",
            "social media", "twitter", "facebook", "bad review",
            "negative review", "report you", "authorities",
        ]
        text_lower = text.lower()
        matches = [p for p in threat_patterns if p in text_lower]
        return {
            "threat_detected": len(matches) > 0,
            "threat_patterns": matches,
            "threat_score": min(1.0, len(matches) * 0.2),
        }

    def full_analysis(self, text: str) -> dict[str, Any]:
        return {
            "keyword_matches": self.detect(text),
            "urgency": self.detect_urgency(text),
            "emotional_manipulation": self.detect_emotional_manipulation(text),
            "contradiction": self.detect_contradiction(text),
            "excessive_certainty": self.detect_excessive_certainty(text),
            "threats": self.detect_threats(text),
        }
