from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from backend.app.ml.feature_engineering import FEATURE_COLUMNS


@dataclass
class AnomalyModel:
    scaler: StandardScaler = field(default_factory=StandardScaler)
    detector: IsolationForest = field(default_factory=lambda: IsolationForest(
        n_estimators=150,
        contamination=0.15,
        random_state=42,
    ))
    fitted: bool = False

    def fit(self, rows: list[dict[str, Any]]):
        X = np.array([[float(row.get(col, 0.0)) for col in FEATURE_COLUMNS] for row in rows], dtype=float)
        X_scaled = self.scaler.fit_transform(X)
        self.detector.fit(X_scaled)
        self.fitted = True

    def score(self, row: dict[str, Any]) -> tuple[float, list[str]]:
        if not self.fitted:
            return self._heuristic_score(row)
        X = np.array([[float(row.get(col, 0.0)) for col in FEATURE_COLUMNS]], dtype=float)
        X_scaled = self.scaler.transform(X)
        anomaly = float(-self.detector.decision_function(X_scaled)[0])
        score = max(0.0, min(100.0, (anomaly + 0.3) * 120))
        return round(score, 2), self._reasons(row)

    def _heuristic_score(self, row: dict[str, Any]) -> tuple[float, list[str]]:
        score = 0.0
        reasons: list[str] = []
        if row.get("product_value", 0) > 15000 and row.get("hours_after_delivery", 999) < 12:
            score += 30
            reasons.append("Unusual high-value fast return")
        if row.get("weight_difference", 0) > 1.0:
            score += 25
            reasons.append("Abnormal weight mismatch")
        if row.get("same_device_account_count", 0) >= 3 and row.get("address_reuse_count", 0) >= 3:
            score += 25
            reasons.append("Suspicious device/address cluster")
        return min(score, 100.0), reasons

    def _reasons(self, row: dict[str, Any]) -> list[str]:
        reasons: list[str] = []
        if row.get("product_value", 0) > 15000:
            reasons.append("Unusual product value")
        if row.get("weight_difference", 0) > 0.5:
            reasons.append("Weight variance outlier")
        if row.get("hours_after_delivery", 999) < 24:
            reasons.append("Very fast return timing")
        if row.get("same_device_account_count", 0) >= 3:
            reasons.append("Device shared by multiple accounts")
        if row.get("address_reuse_count", 0) >= 3:
            reasons.append("Address shared by multiple accounts")
        return reasons[:5]
