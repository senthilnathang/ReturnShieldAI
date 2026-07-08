from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.preprocessing import StandardScaler

from backend.app.ml.feature_engineering import FEATURE_COLUMNS


@dataclass
class StructuredModel:
    random_forest: RandomForestClassifier = field(default_factory=lambda: RandomForestClassifier(
        n_estimators=140,
        max_depth=8,
        random_state=42,
        class_weight="balanced_subsample",
    ))
    gradient_boosting: GradientBoostingClassifier = field(default_factory=lambda: GradientBoostingClassifier(random_state=42))
    histogram_boosting: HistGradientBoostingClassifier = field(default_factory=lambda: HistGradientBoostingClassifier(max_depth=8, random_state=42))
    scaler: StandardScaler = field(default_factory=StandardScaler)
    fitted: bool = False

    def fit(self, rows: list[dict[str, Any]], labels: list[int]):
        X = np.array([[float(row.get(col, 0.0)) for col in FEATURE_COLUMNS] for row in rows], dtype=float)
        y = np.array(labels, dtype=int)
        X_scaled = self.scaler.fit_transform(X)
        self.random_forest.fit(X_scaled, y)
        self.gradient_boosting.fit(X_scaled, y)
        self.histogram_boosting.fit(X_scaled, y)
        self.fitted = True

    def score(self, row: dict[str, Any]) -> tuple[float, list[str]]:
        if not self.fitted:
            return self._heuristic_score(row)
        family_scores = self.family_scores(row)
        probability = float(np.mean(list(family_scores.values()))) / 100.0
        return round(probability * 100.0, 2), self._top_reasons(row)

    def family_scores(self, row: dict[str, Any]) -> dict[str, float]:
        if not self.fitted:
            heuristics, _ = self._heuristic_score(row)
            return {
                "random_forest": round(heuristics, 2),
                "lightgbm_like": round(min(100.0, heuristics + 4.5), 2),
                "xgboost_like": round(min(100.0, heuristics + 2.5), 2),
            }
        X = np.array([[float(row.get(col, 0.0)) for col in FEATURE_COLUMNS]], dtype=float)
        X_scaled = self.scaler.transform(X)
        scores = {
            "random_forest": float(self.random_forest.predict_proba(X_scaled)[0][1]) * 100.0,
            "lightgbm_like": float(self.gradient_boosting.predict_proba(X_scaled)[0][1]) * 100.0,
            "xgboost_like": float(self.histogram_boosting.predict_proba(X_scaled)[0][1]) * 100.0,
        }
        return {name: round(min(100.0, max(0.0, value)), 2) for name, value in scores.items()}

    def _heuristic_score(self, row: dict[str, Any]) -> tuple[float, list[str]]:
        score = 0.0
        reasons: list[str] = []
        if row.get("weight_difference", 0) > 0.5:
            score += 25
            reasons.append("Weight mismatch is a strong fraud signal")
        if row.get("customer_return_count_30d", 0) >= 5:
            score += 20
            reasons.append("Customer has high recent return frequency")
        if row.get("hours_after_delivery", 999) < 24:
            score += 15
            reasons.append("Return was opened very soon after delivery")
        if row.get("previous_fraud_count", 0) > 0:
            score += 20
            reasons.append("Customer has prior fraud history")
        if row.get("address_reuse_count", 0) >= 3:
            score += 15
            reasons.append("Address appears in a risky cluster")
        return min(score, 100.0), reasons

    def _top_reasons(self, row: dict[str, Any]) -> list[str]:
        mapping = [
            ("weight_difference", "Weight mismatch"),
            ("customer_return_count_30d", "High return frequency"),
            ("hours_after_delivery", "Fast return after delivery"),
            ("previous_fraud_count", "Prior fraud history"),
            ("address_reuse_count", "Shared address pattern"),
            ("payment_method_risk_score", "Risky payment method"),
        ]
        ranked = sorted(mapping, key=lambda item: abs(float(row.get(item[0], 0.0))), reverse=True)
        return [label for _, label in ranked[:3]]
