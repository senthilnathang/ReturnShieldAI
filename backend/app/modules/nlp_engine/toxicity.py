from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class ToxicityDetector:
    def __init__(self):
        self._toxicity_patterns = {
            "profanity": [
                r"\bfuck(?:ing|er|ed)?\b", r"\bshit\b", r"\bbitch\b",
                r"\bass\b", r"\bdamn\b", r"\bhell\b", r"\bcrap\b",
                r"\bdick\b", r"\bbastard\b", r"\basshole\b",
            ],
            "threats": [
                r"\bi will ruin\b", r"\bi will destroy\b", r"\byou will regret\b",
                r"\bi know where\b", r"\byou better watch\b",
            ],
            "harassment": [
                r"\bstupid\b", r"\bidiot\b", r"\bmoron\b", r"\bimbecile\b",
                r"\bincompetent\b", r"\bworthless\b", r"\bpathetic\b",
                r"\bdisgusting\b.*\byou\b",
            ],
            "discrimination": [
                r"\bracist\b", r"\bsexist\b", r"\bbigot\b",
            ],
        }
        self._escalation_patterns = {
            "escalation": [
                r"\bmanager\b", r"\bsupervisor\b", r"\bescalate\b",
                r"\bsuperior\b", r"\bdirector\b", r"\bceo\b",
                r"\blegal\b", r"\blawyer\b", r"\battorney\b",
                r"\bcomplaint\b", r"\bbbb\b",
            ],
        }

    def analyze(self, text: str) -> dict[str, Any]:
        if not text:
            return self._empty()
        text_lower = text.lower()
        toxicity_scores = {}
        total_toxicity = 0.0
        detected_categories = []

        for category, patterns in self._toxicity_patterns.items():
            category_score = 0.0
            matches = []
            for p in patterns:
                for m in re.finditer(p, text_lower):
                    matches.append(m.group(0))
                    category_score += 0.25
            toxicity_scores[category] = {
                "score": round(min(1.0, category_score), 4),
                "matches": matches[:10],
                "match_count": len(matches),
            }
            if category_score > 0:
                detected_categories.append(category)
            total_toxicity += category_score

        escalation_scores = {}
        for category, patterns in self._escalation_patterns.items():
            matches = []
            for p in patterns:
                for m in re.finditer(p, text_lower):
                    matches.append(m.group(0))
            escalation_scores[category] = {
                "score": round(min(1.0, len(matches) * 0.2), 4),
                "matches": matches[:10],
                "match_count": len(matches),
            }

        return {
            "toxicity_score": round(min(1.0, total_toxicity), 4),
            "toxicity_categories": toxicity_scores,
            "detected_categories": detected_categories,
            "is_toxic": total_toxicity > 0.3,
            "escalation_signals": escalation_scores,
            "needs_escalation": any(
                s.get("score", 0) > 0.3 for s in escalation_scores.values()
            ),
        }

    def _empty(self) -> dict[str, Any]:
        return {
            "toxicity_score": 0.0,
            "toxicity_categories": {},
            "detected_categories": [],
            "is_toxic": False,
            "escalation_signals": {},
            "needs_escalation": False,
        }
