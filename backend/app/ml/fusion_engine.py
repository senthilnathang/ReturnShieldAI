from __future__ import annotations


def fuse_scores(rule_score: float, structured_ml_score: float, nlp_score: float, anomaly_score: float) -> float:
    final_score = (
        (rule_score * 0.30)
        + (structured_ml_score * 0.30)
        + (nlp_score * 0.25)
        + (anomaly_score * 0.15)
    )
    return round(max(0.0, min(100.0, final_score)), 2)


def decision_from_score(score: float) -> tuple[str, str, str]:
    if score < 40:
        return "AUTO_APPROVE", "LOW", "Approve automatically; no analyst action needed"
    if score < 70:
        return "MANUAL_REVIEW", "MEDIUM", "Queue for analyst review before refund"
    return "HOLD_REFUND_HIGH_RISK", "HIGH", "Hold refund and assign to senior fraud analyst"
