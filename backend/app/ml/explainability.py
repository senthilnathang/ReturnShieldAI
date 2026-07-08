from __future__ import annotations

from typing import Any, Iterable


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


def build_explanation(reasons: Iterable[str], extra_context: dict[str, str] | None = None) -> str:
    extra_context = extra_context or {}
    reasons_list = [reason for reason in reasons if reason]
    if not reasons_list:
        return extra_context.get(
            "fallback",
            "Low-risk return: no material fraud indicators were detected.",
        )

    prefix = extra_context.get("prefix", "Fraud review needed because")
    joined = reasons_list[:3]
    if len(joined) == 1:
        tail = joined[0]
    elif len(joined) == 2:
        tail = f"{joined[0]} and {joined[1]}"
    else:
        tail = f"{joined[0]}, {joined[1]}, and {joined[2]}"
    return f"{prefix} {tail}."


def _driver(label: str, impact: float, detail: str) -> dict[str, Any]:
    return {"label": label, "impact": round(max(0.0, impact), 2), "detail": detail}


def build_explainability_panel(
    *,
    score_breakdown: dict[str, float],
    customer_risk_score: float,
    reason_codes: Iterable[str],
    decision: str,
) -> dict[str, Any]:
    rule_score = float(score_breakdown.get("rule_score", 0.0))
    structured_score = float(score_breakdown.get("structured_ml_score", 0.0))
    nlp_score = float(score_breakdown.get("nlp_score", 0.0))
    anomaly_score = float(score_breakdown.get("anomaly_score", 0.0))
    reason_list = [reason for reason in reason_codes if reason]

    signal_contributions = [
        {
            "label": "Rule engine",
            "score": round(rule_score, 2),
            "weight": 0.30,
            "impact": round(rule_score * 0.30, 2),
            "tone": "risk",
            "detail": "Hard controls fired on shipment timing, weight mismatch, or value thresholds.",
        },
        {
            "label": "Structured ML",
            "score": round(structured_score, 2),
            "weight": 0.30,
            "impact": round(structured_score * 0.30, 2),
            "tone": "risk",
            "detail": "Behavioral profile matches serial-return, address-reuse, or device-sharing patterns.",
        },
        {
            "label": "NLP fraud signals",
            "score": round(nlp_score, 2),
            "weight": 0.25,
            "impact": round(nlp_score * 0.25, 2),
            "tone": "risk",
            "detail": "Language indicates refund pressure, empty-box claims, or repeated fraud scripts.",
        },
        {
            "label": "Anomaly detection",
            "score": round(anomaly_score, 2),
            "weight": 0.15,
            "impact": round(anomaly_score * 0.15, 2),
            "tone": "risk",
            "detail": "The return is an outlier on timing, value, or customer identity combinations.",
        },
        {
            "label": "Customer risk history",
            "score": round(customer_risk_score, 2),
            "weight": 0.0,
            "impact": round(_clamp(customer_risk_score), 2),
            "tone": "risk",
            "detail": "Recent returns, shared address/device signals, and prior fraud labels raise baseline exposure.",
        },
    ]

    ranked = sorted(signal_contributions, key=lambda item: float(item["impact"]), reverse=True)
    strongest = ranked[0] if ranked else None
    second = ranked[1] if len(ranked) > 1 else None

    positive_drivers: list[dict[str, Any]] = []
    negative_drivers: list[dict[str, Any]] = []

    if rule_score >= 15:
        positive_drivers.append(_driver("Triggered return rules", rule_score, "At least one hard rule fired and materially raised the score."))
    if structured_score >= 15:
        positive_drivers.append(_driver("Serial-return pattern", structured_score, "Customer behavior resembles known repeat-abuse patterns."))
    if nlp_score >= 15:
        positive_drivers.append(_driver("Fraud language detected", nlp_score, "The return narrative uses pressure or script-like wording."))
    if anomaly_score >= 15:
        positive_drivers.append(_driver("Outlier transaction", anomaly_score, "The return sits outside normal shipment-return behavior."))
    if customer_risk_score >= 40:
        positive_drivers.append(_driver("Elevated customer history", customer_risk_score, "Recent activity, identity reuse, or prior fraud history is elevated."))

    if customer_risk_score <= 20:
        negative_drivers.append(_driver("Low customer history risk", 20 - customer_risk_score, "The account is not yet building much historical exposure."))
    if rule_score < 10:
        negative_drivers.append(_driver("Limited hard-rule hits", 10 - rule_score, "Only a small subset of rules contributed."))
    if structured_score < 25:
        negative_drivers.append(_driver("Behavior not extreme", 25 - structured_score, "The behavioral model did not see a severe abuse pattern."))
    if nlp_score < 25:
        negative_drivers.append(_driver("Weak text abuse signals", 25 - nlp_score, "Text did not show strong refund-pressure or script reuse."))
    if anomaly_score < 25:
        negative_drivers.append(_driver("Limited outlier evidence", 25 - anomaly_score, "The case is not a strong anomaly across the baseline profile."))

    if not positive_drivers:
        positive_drivers.append(_driver("No dominant risk spike", 0.0, "No single signal overwhelmed the rest of the case evidence."))
    if not negative_drivers:
        negative_drivers.append(_driver("No clear mitigating factors", 0.0, "The case has few signals that reduce fraud concern."))

    if decision == "AUTO_APPROVE":
        why_flagged = "Return stayed below review threshold: no single fraud signal was strong enough to override the clean profile."
    elif decision == "MANUAL_REVIEW":
        why_flagged = "Mixed-risk case: the customer, text, and shipment signals show fraud pressure, but the evidence is not decisive enough for an automatic hold."
    else:
        why_flagged = "High-risk case: rule hits, serial-return behavior, text abuse cues, and anomaly signals all point toward refund fraud."

    if strongest and second:
        why_flagged = f"{why_flagged} Strongest signals: {strongest['label']} and {second['label']}."

    if reason_list:
        why_flagged = f"{why_flagged} Key cues: {', '.join(reason_list[:3]).lower()}."

    return {
        "signal_contributions": signal_contributions,
        "top_positive_drivers": positive_drivers[:3],
        "top_negative_drivers": negative_drivers[:3],
        "why_flagged_summary": why_flagged,
    }


def recommended_action(decision: str) -> str:
    mapping = {
        "AUTO_APPROVE": "Approve refund automatically",
        "MANUAL_REVIEW": "Review return manually",
        "HOLD_REFUND_HIGH_RISK": "Hold refund and assign to senior fraud analyst",
    }
    return mapping.get(decision, "Review manually")
