from __future__ import annotations


def fuse_scores(rule_score: float, structured_ml_score: float, nlp_score: float, anomaly_score: float) -> float:
    if nlp_score == 0 and anomaly_score == 0:
        final_score = (rule_score * 0.35) + (structured_ml_score * 0.65)
    else:
        final_score = (
            (rule_score * 0.25)
            + (structured_ml_score * 0.45)
            + (nlp_score * 0.15)
            + (anomaly_score * 0.05)
        )
    return round(max(0.0, min(100.0, final_score)), 2)


def decision_from_score(score: float) -> tuple[str, str, str]:
    if score < 40:
        return "AUTO_APPROVE", "LOW", "Approve automatically; no analyst action needed"
    if score < 70:
        return "MANUAL_REVIEW", "MEDIUM", "Queue for analyst review before refund"
    return "HOLD_REFUND_HIGH_RISK", "HIGH", "Hold refund and assign to senior fraud analyst"
