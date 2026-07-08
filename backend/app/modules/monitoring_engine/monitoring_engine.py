from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class DriftReport:
    drift_detected: bool
    drift_share: float
    drifted_columns: list[dict[str, Any]]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class EvidentlyMonitor:
    def __init__(self, reference_data: Any = None):
        self.reference_data = reference_data

    def set_reference(self, data: Any) -> None:
        self.reference_data = data

    def check_drift(self, current_data: Any) -> DriftReport:
        try:
            from evidently.metrics import DataDriftPreset
            from evidently.report import Report
            if self.reference_data is None or current_data is None:
                return DriftReport(drift_detected=False, drift_share=0.0, drifted_columns=[])
            report = Report(metrics=[DataDriftPreset()])
            report.run(reference_data=self.reference_data, current_data=current_data)
            raw = report.as_dict()
            drift_share = 0.0
            drifted_cols = []
            for metric in raw.get("metrics", []):
                result = metric.get("result", {})
                drift_share = result.get("drift_share", 0.0)
                for col, col_data in result.get("drift_by_columns", {}).items():
                    if col_data.get("drift_detected", False):
                        drifted_cols.append({
                            "column": col,
                            "drift_score": col_data.get("drift_score", 0.0),
                            "stat_test": col_data.get("stattest_name", ""),
                        })
            return DriftReport(
                drift_detected=drift_share > 0.3,
                drift_share=drift_share,
                drifted_columns=drifted_cols,
            )
        except Exception:
            return DriftReport(drift_detected=False, drift_share=0.0, drifted_columns=[])


class ModelPerformanceTracker:
    def __init__(self):
        self.metrics_history: list[dict[str, Any]] = []

    def log_prediction(self, features: dict[str, float], prediction: float,
                       actual: float | None = None, latency_ms: float = 0.0) -> None:
        self.metrics_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "features": features,
            "prediction": prediction,
            "actual": actual,
            "latency_ms": latency_ms,
        })
        if len(self.metrics_history) > 10000:
            self.metrics_history = self.metrics_history[-5000:]

    def get_recent_metrics(self, n: int = 100) -> dict[str, Any]:
        recent = self.metrics_history[-n:] if self.metrics_history else []
        if not recent:
            return {"avg_prediction": 0, "samples": 0}
        predictions = [m["prediction"] for m in recent]
        return {
            "avg_prediction": round(sum(predictions) / len(predictions), 2),
            "max_prediction": round(max(predictions), 2),
            "min_prediction": round(min(predictions), 2),
            "samples": len(recent),
            "avg_latency_ms": round(sum(m["latency_ms"] for m in recent) / len(recent), 2),
        }


class MonitoringEngine:
    def __init__(self):
        self.drift_monitor = EvidentlyMonitor()
        self.performance_tracker = ModelPerformanceTracker()

    def check_data_drift(self, current_data: Any) -> DriftReport:
        return self.drift_monitor.check_drift(current_data)

    def log_scoring_event(self, features: dict[str, float], prediction: float,
                          actual: float | None = None, latency_ms: float = 0.0) -> None:
        self.performance_tracker.log_prediction(features, prediction, actual, latency_ms)

    def get_performance_summary(self) -> dict[str, Any]:
        return self.performance_tracker.get_recent_metrics()
