from __future__ import annotations

from typing import Any, Optional


class EvidenceEngine:
    def build(
        self,
        text: str,
        fraud_probability: float,
        nlp_score: int,
        intents: dict[str, Any],
        keyword_analysis: dict[str, Any],
        sentiment: dict[str, Any],
        toxicity: dict[str, Any],
        entities: dict[str, Any],
        similar_cases: list[dict[str, Any]],
        confidence: float,
    ) -> list[dict[str, Any]]:
        evidence = []
        evidence.extend(self._pattern_evidence(keyword_analysis, intents))
        evidence.extend(self._sentiment_evidence(sentiment, toxicity))
        evidence.extend(self._similarity_evidence(similar_cases))
        evidence.extend(self._entity_evidence(entities))
        evidence.extend(self._score_evidence(fraud_probability, nlp_score, confidence))
        return evidence

    def _pattern_evidence(
        self, keyword_analysis: dict[str, Any], intents: dict[str, Any]
    ) -> list[dict[str, Any]]:
        items = []
        detected_intents = intents.get("intents", {})
        if detected_intents:
            primary = intents.get("primary_intent")
            primary_score = intents.get("primary_score", 0.0)
            items.append({
                "type": "fraud_intent",
                "severity": "high" if primary_score > 0.7 else "medium",
                "title": f"Fraud Intent Detected: {primary}",
                "detail": f"Primary intent '{primary}' with score {primary_score:.2f}. "
                          f"Total {len(detected_intents)} intents detected.",
                "score": round(primary_score * 100, 2),
                "indicators": list(detected_intents.keys()),
            })

        urgency = keyword_analysis.get("urgency", {})
        if urgency.get("urgency_detected"):
            items.append({
                "type": "urgency",
                "severity": "medium",
                "title": "Refund Urgency Detected",
                "detail": f"Found {urgency.get('urgency_count', 0)} urgency patterns: "
                          f"{', '.join(urgency.get('urgency_patterns', []))}",
                "score": round(urgency.get("urgency_score", 0) * 100, 2),
            })

        threats = keyword_analysis.get("threats", {})
        if threats.get("threat_detected"):
            items.append({
                "type": "threat",
                "severity": "high",
                "title": "Chargeback Threat Detected",
                "detail": f"Found {len(threats.get('threat_patterns', []))} threat patterns",
                "score": round(threats.get("threat_score", 0) * 100, 2),
            })

        contradiction = keyword_analysis.get("contradiction", {})
        if contradiction.get("contradiction_detected"):
            items.append({
                "type": "contradiction",
                "severity": "high",
                "title": "Contradictory Statements",
                "detail": f"Found {len(contradiction.get('contradictions', []))} contradictions",
                "score": 80.0,
            })

        manipulation = keyword_analysis.get("emotional_manipulation", {})
        if manipulation.get("emotional_manipulation"):
            items.append({
                "type": "emotional_manipulation",
                "severity": "medium",
                "title": "Emotional Manipulation Detected",
                "detail": f"Found {len(manipulation.get('emotional_patterns', []))} emotional patterns",
                "score": round(manipulation.get("emotional_score", 0) * 100, 2),
            })

        certainty = keyword_analysis.get("excessive_certainty", {})
        if certainty.get("excessive_certainty"):
            items.append({
                "type": "excessive_certainty",
                "severity": "low",
                "title": "Excessive Certainty Detected",
                "detail": f"Unnaturally definite language found: "
                          f"{', '.join(certainty.get('certainty_patterns', []))}",
                "score": round(certainty.get("certainty_score", 0) * 100, 2),
            })

        return items

    def _sentiment_evidence(
        self, sentiment: dict[str, Any], toxicity: dict[str, Any]
    ) -> list[dict[str, Any]]:
        items = []
        if sentiment.get("frustration", 0) > 0.5:
            items.append({
                "type": "frustration",
                "severity": "medium",
                "title": "High Frustration Level",
                "detail": f"Frustration score: {sentiment['frustration']:.2f}",
                "score": round(sentiment["frustration"] * 100, 2),
            })
        if sentiment.get("aggression", 0) > 0.5:
            items.append({
                "type": "aggression",
                "severity": "high",
                "title": "Aggressive Language Detected",
                "detail": f"Aggression score: {sentiment['aggression']:.2f}",
                "score": round(sentiment["aggression"] * 100, 2),
            })
        if toxicity.get("is_toxic"):
            items.append({
                "type": "toxicity",
                "severity": "high",
                "title": "Toxic Language Detected",
                "detail": f"Toxicity score: {toxicity.get('toxicity_score', 0):.2f}",
                "score": round(toxicity.get("toxicity_score", 0) * 100, 2),
            })
        if toxicity.get("needs_escalation"):
            items.append({
                "type": "escalation",
                "severity": "high",
                "title": "Escalation Signals Detected",
                "detail": "Customer mentions management, legal, or escalation",
                "score": 75.0,
            })
        return items

    def _similarity_evidence(
        self, similar_cases: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        items = []
        if not similar_cases:
            return items
        high_similarity = [c for c in similar_cases if c.get("score", 0) >= 75]
        if high_similarity:
            items.append({
                "type": "similar_cases",
                "severity": "high",
                "title": f"Matches {len(high_similarity)} Confirmed Fraud Cases",
                "detail": f"Top similarity: {high_similarity[0].get('score', 0):.1f}%. "
                          f"Common patterns: {self._extract_common_patterns(high_similarity)}",
                "score": round(sum(c.get("score", 0) for c in high_similarity) / len(high_similarity), 2),
                "case_ids": [c.get("metadata", {}).get("case_id") for c in high_similarity if c.get("metadata")],
            })
        medium_similarity = [c for c in similar_cases if 50 <= c.get("score", 0) < 75]
        if medium_similarity:
            items.append({
                "type": "similar_patterns",
                "severity": "medium",
                "title": f"Similar to {len(medium_similarity)} Historical Cases",
                "detail": f"Similarity range: {medium_similarity[-1].get('score', 0):.1f}% - {medium_similarity[0].get('score', 0):.1f}%",
                "score": round(sum(c.get("score", 0) for c in medium_similarity) / len(medium_similarity), 2),
            })
        return items

    def _extract_common_patterns(self, cases: list[dict[str, Any]]) -> str:
        fraud_types = set()
        for c in cases:
            meta = c.get("metadata", {})
            ft = meta.get("fraud_type") or meta.get("risk_level") or meta.get("decision")
            if ft:
                fraud_types.add(str(ft))
        return ", ".join(sorted(fraud_types)) if fraud_types else "fraudulent behavior"

    def _entity_evidence(self, entities: dict[str, Any]) -> list[dict[str, Any]]:
        items = []
        if entities.get("serial_numbers"):
            items.append({
                "type": "serial_mismatch_check",
                "severity": "medium",
                "title": "Serial Number References Found",
                "detail": f"Customer referenced {len(entities['serial_numbers'])} serial number(s)",
                "score": 50.0,
            })
        if entities.get("imei"):
            items.append({
                "type": "imei_reference",
                "severity": "medium",
                "title": "IMEI References Found",
                "detail": f"Customer referenced {len(entities['imei'])} IMEI number(s)",
                "score": 50.0,
            })
        return items

    def _score_evidence(
        self, fraud_probability: float, nlp_score: int, confidence: float
    ) -> list[dict[str, Any]]:
        return [{
            "type": "nlp_score_summary",
            "severity": "high" if nlp_score >= 75 else "medium" if nlp_score >= 40 else "low",
            "title": f"NLP Fraud Score: {nlp_score}/100",
            "detail": (
                f"Fraud probability: {fraud_probability:.1%}. "
                f"Confidence: {confidence:.1%}. "
                f"Risk: {'HIGH' if nlp_score >= 75 else 'MEDIUM' if nlp_score >= 40 else 'LOW'}"
            ),
            "score": float(nlp_score),
        }]

    def generate_explanation(self, evidence: list[dict[str, Any]]) -> str:
        if not evidence:
            return "No fraud indicators detected in text."
        high = [e for e in evidence if e.get("severity") == "high"]
        medium = [e for e in evidence if e.get("severity") == "medium"]
        parts = []
        parts.append(f"Detected {len(high)} high-severity and {len(medium)} medium-severity indicators.")
        for e in evidence:
            parts.append(f"- {e['title']}: {e.get('detail', '')}")
        return "\n".join(parts)
