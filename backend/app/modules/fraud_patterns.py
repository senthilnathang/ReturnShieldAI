from __future__ import annotations

from typing import Any


FRAUD_PATTERNS = [
    {
        "id": "wardrobing",
        "name": "Wardrobing",
        "description": "Customer purchases items, uses them once, and returns them for a full refund.",
        "severity": "MEDIUM",
        "rules": ["return_rate_90d > 0.5", "hours_after_delivery < 48", "condition_reported == 'used'"],
        "ml_features": ["return_rate_90d", "hours_after_delivery", "lifetime_returns"],
        "nlp_features": [],
        "graph_features": [],
        "recommended_actions": ["Deduct restocking fee", "Flag for return frequency monitoring"],
    },
    {
        "id": "empty_box",
        "name": "Empty Box Fraud",
        "description": "Customer claims the box arrived empty and demands a refund.",
        "severity": "HIGH",
        "rules": ["expected_weight - returned_weight > 0.5", "condition_reported == 'empty_box'"],
        "ml_features": ["weight_difference", "expected_weight", "returned_weight"],
        "nlp_features": ["empty box", "box was empty", "nothing inside"],
        "graph_features": [],
        "recommended_actions": ["Request delivery photo evidence", "Flag for carrier investigation"],
    },
    {
        "id": "item_not_received",
        "name": "Item Not Received (INR)",
        "description": "Customer claims the item was never delivered despite delivery confirmation.",
        "severity": "HIGH",
        "rules": ["delivery_status == 'delivered'", "hours_after_delivery > 48"],
        "ml_features": ["hours_after_delivery"],
        "nlp_features": ["item not received", "never received", "did not receive"],
        "graph_features": [],
        "recommended_actions": ["Verify delivery proof of delivery", "Check carrier GPS logs"],
    },
    {
        "id": "fake_damage",
        "name": "Fake Damage Claim",
        "description": "Customer falsely claims the product arrived damaged to obtain a refund without returning the item.",
        "severity": "MEDIUM",
        "rules": ["condition_reported == 'damaged'", "product_value > 200"],
        "ml_features": ["product_value"],
        "nlp_features": ["damaged", "broken", "defective", "arrived damaged"],
        "graph_features": [],
        "recommended_actions": ["Request photo evidence of damage", "Compare with shipping photos"],
    },
    {
        "id": "refund_abuse",
        "name": "Refund Abuse",
        "description": "Customer repeatedly requests refunds using aggressive or threatening language.",
        "severity": "HIGH",
        "rules": ["customer_return_count_30d >= 3", "chargeback_threat_flag"],
        "ml_features": ["customer_return_count_30d", "chargeback_count", "previous_fraud_count"],
        "nlp_features": ["chargeback", "refund or else", "dispute", "lawyer"],
        "graph_features": [],
        "recommended_actions": ["Restrict return privileges", "Flag account for monitoring"],
    },
    {
        "id": "serial_returner",
        "name": "Serial Returner",
        "description": "Customer systematically returns a high percentage of purchases across multiple categories.",
        "severity": "MEDIUM",
        "rules": ["lifetime_returns / lifetime_orders > 0.4", "lifetime_orders > 10"],
        "ml_features": ["return_rate_30d", "return_rate_90d", "lifetime_returns", "lifetime_orders"],
        "nlp_features": [],
        "graph_features": [],
        "recommended_actions": ["Apply return frequency limit", "Flag for account review"],
    },
    {
        "id": "coupon_abuse",
        "name": "Coupon Abuse",
        "description": "Customer uses multiple coupons/discount codes across different accounts.",
        "severity": "MEDIUM",
        "rules": ["payment_method_risk_score > 50"],
        "ml_features": ["payment_method_risk_score"],
        "nlp_features": [],
        "graph_features": ["shared_address_count", "shared_device_count", "shared_payment_count"],
        "recommended_actions": ["Limit coupon usage per address/device", "Investigate linked accounts"],
    },
    {
        "id": "address_farming",
        "name": "Address Farming",
        "description": "Coordinated fraud ring using the same address for multiple fraudulent returns.",
        "severity": "HIGH",
        "rules": ["address_reuse_count >= 3"],
        "ml_features": ["address_reuse_count"],
        "nlp_features": [],
        "graph_features": ["shared_address_count", "connected_customers_count", "component_size"],
        "recommended_actions": ["Blacklist address", "Investigate linked accounts", "Notify fraud team"],
    },
    {
        "id": "refund_ring",
        "name": "Refund Ring",
        "description": "Organized group using shared refund accounts, devices, and scripts to defraud.",
        "severity": "CRITICAL",
        "rules": ["shared_refund_account_count >= 2", "connected_customers_count >= 3"],
        "ml_features": ["same_device_account_count", "address_reuse_count", "previous_fraud_count"],
        "nlp_features": [],
        "graph_features": ["ring_risk_score", "shared_refund_account_count", "shortest_path_to_fraud",
                           "fraud_neighbor_count", "community_score", "graph_density"],
        "recommended_actions": ["Escalate to fraud ring task force", "Freeze all linked accounts",
                                "File law enforcement report", "Update fraud rules for pattern"],
    },
    {
        "id": "return_washing",
        "name": "Return Washing",
        "description": "Customer returns a different/fake item while claiming to return the original product.",
        "severity": "HIGH",
        "rules": ["expected_weight - returned_weight > 0.3", "condition_reported == 'unused'"],
        "ml_features": ["weight_difference", "expected_weight", "returned_weight"],
        "nlp_features": [],
        "graph_features": [],
        "recommended_actions": ["Inspect returned item against order", "Flag for warehouse review"],
    },
]


def get_pattern_by_id(pattern_id: str) -> dict[str, Any] | None:
    return next((p for p in FRAUD_PATTERNS if p["id"] == pattern_id), None)


def match_patterns(case_data: dict[str, Any]) -> list[dict[str, Any]]:
    matches = []
    for pattern in FRAUD_PATTERNS:
        score = _pattern_match_score(pattern, case_data)
        if score > 0:
            matches.append({"pattern": pattern["id"], "name": pattern["name"],
                            "severity": pattern["severity"], "match_score": score})
    return sorted(matches, key=lambda x: x["match_score"], reverse=True)


def _pattern_match_score(pattern: dict[str, Any], data: dict[str, Any]) -> float:
    score = 0.0
    rules = pattern.get("rules", [])
    if not rules:
        return 0.0
    for rule in rules:
        try:
            if _eval_rule(rule, data):
                score += 100.0 / len(rules)
        except Exception:
            pass
    return round(min(100.0, score), 1)


def _eval_rule(rule: str, data: dict[str, Any]) -> bool:
    local_vars = {}
    for key, val in data.items():
        if isinstance(val, (int, float, str, bool)):
            local_vars[key] = val
    try:
        return bool(eval(rule, {"__builtins__": {}}, local_vars))
    except Exception:
        return False
