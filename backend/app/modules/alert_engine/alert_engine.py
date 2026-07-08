from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


class AlertProvider(Protocol):
    def send(self, title: str, message: str, severity: str, metadata: dict[str, Any] | None = None) -> bool: ...


class SlackProvider:
    def __init__(self, webhook_url: str | None = None):
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL", "")

    def send(self, title: str, message: str, severity: str, metadata: dict[str, Any] | None = None) -> bool:
        if not self.webhook_url:
            return False
        try:
            import httpx
            color = {"HIGH": "danger", "MEDIUM": "warning", "LOW": "good"}.get(severity, "#ccc")
            payload = {
                "attachments": [{
                    "color": color,
                    "title": f"[{severity}] {title}",
                    "text": message,
                    "fields": [{"title": k, "value": str(v), "short": True} for k, v in (metadata or {}).items()],
                    "footer": "ReturnShield AI Alert Engine",
                    "ts": datetime.utcnow().timestamp(),
                }]
            }
            resp = httpx.post(self.webhook_url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False


class EmailProvider:
    def __init__(self):
        pass

    def send(self, title: str, message: str, severity: str, metadata: dict[str, Any] | None = None) -> bool:
        return True


class WebhookProvider:
    def __init__(self, url: str | None = None):
        self.url = url or os.getenv("ALERT_WEBHOOK_URL", "")

    def send(self, title: str, message: str, severity: str, metadata: dict[str, Any] | None = None) -> bool:
        if not self.url:
            return False
        try:
            import httpx
            payload = {"title": title, "message": message, "severity": severity, "metadata": metadata or {}, "timestamp": datetime.utcnow().isoformat()}
            resp = httpx.post(self.url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False


@dataclass
class AlertRule:
    name: str
    description: str
    severity: str
    condition: str
    providers: list[str]


ALERT_RULES = [
    AlertRule("high_risk_case", "Case scored as high risk", "HIGH", "risk_level == 'HIGH'", ["slack", "email"]),
    AlertRule("fraud_ring_detected", "Fraud ring detected in graph", "HIGH", "ring_risk_score >= 50", ["slack"]),
    AlertRule("vip_customer_flag", "VIP customer flagged as risk", "MEDIUM", "customer_risk_score >= 60 and is_vip", ["slack", "email"]),
    AlertRule("high_value_return", "High value return flagged", "HIGH", "product_value > 5000 and risk_level != 'LOW'", ["slack"]),
    AlertRule("repeated_fraud_pattern", "Customer with repeated fraud pattern", "MEDIUM", "previous_fraud_count >= 2", ["slack"]),
]


class AlertEngine:
    def __init__(self):
        self.providers: dict[str, AlertProvider] = {
            "slack": SlackProvider(),
            "email": EmailProvider(),
            "webhook": WebhookProvider(),
        }
        self.rules = ALERT_RULES

    def evaluate_and_alert(self, case_data: dict[str, Any]) -> list[dict[str, Any]]:
        alerts_fired = []
        for rule in self.rules:
            if self._matches_condition(rule.condition, case_data):
                result = self._fire_alert(rule, case_data)
                alerts_fired.append(result)
        return alerts_fired

    def _matches_condition(self, condition: str, data: dict[str, Any]) -> bool:
        try:
            risk_level = data.get("risk_level", "")
            ring_risk = data.get("graph_fraud", {}).get("ring_risk_score", 0)
            customer_risk = data.get("customer_risk_score", 0)
            is_vip = data.get("is_vip", False)
            product_value = data.get("product_value", 0)
            previous_fraud = data.get("previous_fraud_count", 0)
            return bool(eval(condition, {"__builtins__": {}}, {
                "risk_level": risk_level, "ring_risk_score": ring_risk,
                "customer_risk_score": customer_risk, "is_vip": is_vip,
                "product_value": product_value, "previous_fraud_count": previous_fraud,
            }))
        except Exception:
            return False

    def _fire_alert(self, rule: AlertRule, data: dict[str, Any]) -> dict[str, Any]:
        title = f"[{rule.severity}] {rule.name}"
        message = f"{rule.description}: {data.get('case_id', 'N/A')}"
        results = {}
        for provider_name in rule.providers:
            provider = self.providers.get(provider_name)
            if provider:
                success = provider.send(title, message, rule.severity, {
                    "case_id": str(data.get("case_id", "")),
                    "risk_score": data.get("risk_score", 0),
                    "customer": data.get("customer_name", ""),
                })
                results[provider_name] = "sent" if success else "failed"
        return {"rule": rule.name, "severity": rule.severity, "title": title, "providers": results, "timestamp": datetime.utcnow().isoformat()}
