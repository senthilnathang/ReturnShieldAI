from __future__ import annotations

from datetime import datetime
from typing import Any


class TimelineEngine:
    def build_timeline(self, customer: Any, order: Any, return_record: Any,
                       case: Any | None = None, feedback: Any | None = None,
                       advanced_signals: dict[str, Any] | None = None) -> list[dict[str, str]]:
        events: list[dict[str, str]] = []

        if customer and hasattr(customer, 'created_at') and customer.created_at:
            events.append({
                "label": "Account created",
                "time": customer.created_at.isoformat() if hasattr(customer.created_at, 'isoformat') else str(customer.created_at),
                "type": "customer",
                "detail": f"Customer {customer.name} created account.",
            })

        if order:
            if order.delivery_date:
                events.append({
                    "label": "Order placed",
                    "time": order.delivery_date.isoformat() if hasattr(order.delivery_date, 'isoformat') else str(order.delivery_date),
                    "type": "order",
                    "detail": f"Order for {order.product_name} (${order.product_value}) placed.",
                })

        if return_record:
            events.append({
                "label": "Return requested",
                "time": return_record.created_at.isoformat() if hasattr(return_record.created_at, 'isoformat') else str(return_record.created_at),
                "type": "return",
                "detail": f"Return reason: {return_record.return_reason[:100]}",
            })
            if return_record.chat_transcript:
                events.append({
                    "label": "Customer support chat",
                    "time": return_record.created_at.isoformat() if hasattr(return_record.created_at, 'isoformat') else str(return_record.created_at),
                    "type": "communication",
                    "detail": f"Chat transcript: {return_record.chat_transcript[:100]}",
                })
            if return_record.email_text:
                events.append({
                    "label": "Customer email",
                    "time": return_record.created_at.isoformat() if hasattr(return_record.created_at, 'isoformat') else str(return_record.created_at),
                    "type": "communication",
                    "detail": f"Email text: {return_record.email_text[:100]}",
                })

        if case:
            events.append({
                "label": "Case scored",
                "time": case.created_at.isoformat() if hasattr(case.created_at, 'isoformat') else str(case.created_at),
                "type": "decision",
                "detail": f"Risk score: {case.risk_score}, Decision: {case.decision}",
            })

        if advanced_signals:
            graph = advanced_signals.get("graph_fraud", {})
            if graph.get("ring_risk_score", 0) >= 40:
                events.append({
                    "label": "Fraud ring alert",
                    "time": datetime.utcnow().isoformat(),
                    "type": "alert",
                    "detail": f"Fraud ring detected: {graph.get('summary', '')}",
                })

        if feedback:
            events.append({
                "label": "Analyst reviewed",
                "time": feedback.created_at.isoformat() if hasattr(feedback.created_at, 'isoformat') else str(feedback.created_at),
                "type": "review",
                "detail": f"Decision: {feedback.analyst_decision}, Label: {feedback.confirmed_label}",
            })

        return sorted(events, key=lambda e: e["time"], reverse=True)
