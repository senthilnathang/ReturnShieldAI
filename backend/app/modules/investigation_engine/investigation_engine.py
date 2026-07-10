from __future__ import annotations

import json
import logging
from typing import Any

from backend.app.modules.llm import LLMClient, get_llm_client

logger = logging.getLogger("returnshield.investigation")


SYSTEM_PROMPT = """You are an AI fraud investigation assistant for ReturnShield AI.
Analyze the case evidence and provide:
1. Executive summary of the fraud risk
2. Fraud probability assessment
3. Evidence summary organized by category
4. Reasoning behind the assessment
5. Recommended next actions
6. Confidence level

Base your analysis only on the evidence provided. Be specific and cite evidence."""


class InvestigationEngine:
    def __init__(self, prompt_template: str | None = None, llm_client: LLMClient | None = None):
        self.prompt_template = prompt_template or SYSTEM_PROMPT
        self.llm_client = llm_client if llm_client is not None else get_llm_client()

    def generate_report(self, case_data: dict[str, Any]) -> dict[str, Any]:
        evidence = case_data.get("evidence", [])
        graph = case_data.get("graph_fraud", {})
        signals = case_data.get("advanced_signals", {})
        scores = case_data.get("scores", {})
        timeline = case_data.get("timeline", [])
        reason_codes = case_data.get("reason_codes", [])

        fraud_probability = self._calculate_fraud_probability(scores, graph, evidence)
        evidence_summary = self._summarize_evidence(evidence)
        recommendation = self._generate_recommendation(fraud_probability, scores, reason_codes)

        executive_summary = self._build_summary(fraud_probability, scores, reason_codes, graph)
        reasoning = self._build_reasoning(reason_codes, scores, graph)

        llm_narrative = self._llm_narrative(case_data, fraud_probability, evidence_summary, reasoning)
        if llm_narrative is not None:
            executive_summary = llm_narrative.get("executive_summary", executive_summary) or executive_summary
            llm_reasoning = llm_narrative.get("reasoning")
            if isinstance(llm_reasoning, list) and llm_reasoning:
                reasoning = llm_reasoning
            llm_recs = llm_narrative.get("recommendations")
            if isinstance(llm_recs, list) and llm_recs:
                recommendation = [str(r) for r in llm_recs][:5]

        return {
            "executive_summary": executive_summary,
            "fraud_probability": fraud_probability,
            "fraud_probability_label": self._probability_label(fraud_probability),
            "evidence_summary": evidence_summary,
            "reasoning": reasoning,
            "recommendations": recommendation,
            "confidence": self._calculate_confidence(scores, evidence, graph),
            "key_signals": self._extract_key_signals(scores, graph, signals),
            "timeline_highlights": timeline[:5] if timeline else [],
            "llm_enabled": llm_narrative is not None,
        }

    def _llm_narrative(
        self,
        case_data: dict[str, Any],
        fraud_probability: float,
        evidence_summary: list[dict[str, Any]],
        reasoning: list[str],
    ) -> dict[str, Any] | None:
        """Generate narrative insights via the LLM.

        Returns ``None`` when the LLM is disabled or the call fails so the
        engine transparently falls back to heuristic output.
        """
        client = self.llm_client
        if client is None or not client.is_enabled:
            return None

        user_prompt = self._build_user_prompt(
            case_data, fraud_probability, evidence_summary, reasoning
        )
        try:
            result = client.chat_json(system=self.prompt_template, user=user_prompt)
        except Exception as exc:
            logger.warning("LLM investigation call failed: %s", exc)
            return None
        if result is None:
            logger.info("LLM investigation unavailable; using heuristic report")
        return result

    @staticmethod
    def _build_user_prompt(
        case_data: dict[str, Any],
        fraud_probability: float,
        evidence_summary: list[dict[str, Any]],
        reasoning: list[str],
    ) -> str:
        return json.dumps({
            "case_id": case_data.get("case_id"),
            "customer_name": case_data.get("customer_name"),
            "fraud_probability": fraud_probability,
            "risk_score": case_data.get("risk_score"),
            "product_value": case_data.get("product_value"),
            "reason_codes": case_data.get("reason_codes", []),
            "scores": case_data.get("scores", {}),
            "graph_fraud": case_data.get("graph_fraud", {}),
            "evidence_summary": evidence_summary,
            "heuristic_reasoning": reasoning,
        }, default=str)

    def _calculate_fraud_probability(self, scores: dict[str, Any], graph: dict[str, Any],
                                     evidence: list[dict[str, Any]]) -> float:
        final_score = scores.get("final_score", 50.0)
        ring_risk = graph.get("ring_risk_score", 0)
        evidence_boost = min(20.0, len([e for e in evidence if e.get("confidence", 0) > 70]) * 5.0)
        probability = final_score * 0.7 + ring_risk * 0.2 + evidence_boost
        return round(max(0.0, min(100.0, probability)), 1)

    def _probability_label(self, prob: float) -> str:
        if prob >= 70:
            return "HIGH"
        if prob >= 40:
            return "MEDIUM"
        return "LOW"

    def _summarize_evidence(self, evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        categories = {}
        for item in evidence:
            cat = item.get("category", "other")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(item)
        return [{"category": cat, "items": items, "count": len(items),
                 "max_confidence": max((i.get("confidence", 0) for i in items), default=0)}
                for cat, items in categories.items()]

    def _build_summary(self, probability: float, scores: dict[str, Any],
                       reason_codes: list[str], graph: dict[str, Any]) -> str:
        label = self._probability_label(probability)
        parts = [
            f"This is a {label.lower()}-probability fraud case ({probability:.0f}% fraud probability).",
        ]
        if reason_codes:
            parts.append(f"Key indicators: {', '.join(reason_codes[:3])}.")
        if graph.get("ring_risk_score", 0) > 30:
            parts.append(f"Fraud ring risk detected (score: {graph['ring_risk_score']}).")
        return " ".join(parts)

    def _build_reasoning(self, reason_codes: list[str], scores: dict[str, Any],
                         graph: dict[str, Any]) -> list[str]:
        reasoning = []
        for code in reason_codes[:5]:
            reasoning.append(f"Signal: {code}")
        for key in ["rule_score", "structured_ml_score", "nlp_score", "anomaly_score"]:
            val = scores.get(key, 0)
            if val >= 25:
                reasoning.append(f"{key.replace('_', ' ').title()}: {val:.1f} (elevated)")
        if graph.get("ring_risk_score", 0) > 30:
            reasoning.append(f"Fraud ring risk: {graph['ring_risk_score']} ({graph.get('connected_customers_count', 0)} connected accounts)")
        return reasoning[:8]

    def _generate_recommendation(self, probability: float, scores: dict[str, Any],
                                 reason_codes: list[str]) -> list[str]:
        recs = []
        if probability >= 70:
            recs.append("Hold refund and escalate to senior fraud analyst")
            recs.append("Flag customer account for monitoring")
        elif probability >= 40:
            recs.append("Request additional verification before processing refund")
            recs.append("Review return history for similar patterns")
        else:
            recs.append("Approve return — no significant fraud indicators")
        if any("shared address" in r.lower() or "device" in r.lower() for r in reason_codes):
            recs.append("Investigate linked accounts for coordinated fraud")
        if any("chargeback" in r.lower() or "threat" in r.lower() for r in reason_codes):
            recs.append("Document chargeback threat for dispute preparation")
        return recs[:5]

    def _calculate_confidence(self, scores: dict[str, Any], evidence: list[dict[str, Any]],
                              graph: dict[str, Any]) -> float:
        evidence_count = len(evidence)
        score_confidence = min(50.0, sum(scores.values()) / max(len(scores), 1))
        evidence_confidence = min(30.0, evidence_count * 5.0)
        graph_confidence = min(20.0, graph.get("ring_risk_score", 0) * 0.2)
        return round(min(100.0, score_confidence + evidence_confidence + graph_confidence), 1)

    def _extract_key_signals(self, scores: dict[str, Any], graph: dict[str, Any],
                             signals: dict[str, Any]) -> list[dict[str, Any]]:
        key_signals = []
        for name, val in [("Rule Engine", scores.get("rule_score", 0)),
                          ("Structured ML", scores.get("structured_ml_score", 0)),
                          ("NLP Analysis", scores.get("nlp_score", 0)),
                          ("Anomaly Detection", scores.get("anomaly_score", 0))]:
            if val >= 20:
                key_signals.append({"signal": name, "score": round(val, 1), "weight": "HIGH" if val >= 60 else "MEDIUM"})
        if graph.get("ring_risk_score", 0) >= 30:
            key_signals.append({"signal": "Fraud Ring Detection", "score": float(graph["ring_risk_score"]), "weight": "HIGH"})
        return key_signals[:8]
