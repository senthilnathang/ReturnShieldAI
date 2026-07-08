from __future__ import annotations

from typing import Any

import numpy as np

from backend.app.ml.feature_engineering import FEATURE_COLUMNS


class ShapExplainabilityEngine:
    def __init__(self):
        self._explainer = None
        self._model = None
        self._feature_names = FEATURE_COLUMNS

    def fit(self, model: Any, background_data: np.ndarray | None = None) -> None:
        import shap
        if hasattr(model, "random_forest") and hasattr(model.random_forest, "predict_proba"):
            self._model = model.random_forest
        else:
            self._model = model
        self._explainer = shap.TreeExplainer(
            self._model,
            data=background_data,
            feature_perturbation="tree_path_dependent",
        )

    def explain(self, features: dict[str, float] | np.ndarray) -> dict[str, Any]:
        if self._explainer is None:
            return self._fallback_explain(features)
        if isinstance(features, dict):
            X = np.array([[float(features.get(col, 0.0)) for col in self._feature_names]], dtype=float)
        else:
            X = np.array([features], dtype=float) if features.ndim == 1 else features
        shap_values = self._explainer.shap_values(X)
        expected = float(self._explainer.expected_value)
        if isinstance(shap_values, list):
            sv = shap_values[1] if len(shap_values) > 1 else shap_values[0]
        else:
            sv = shap_values
        return self._format_explanation(sv[0], expected, self._feature_names, X[0])

    def _format_explanation(self, shap_values: np.ndarray, expected: float,
                            feature_names: list[str], raw_features: np.ndarray) -> dict[str, Any]:
        positive_indices = np.argsort(shap_values)[::-1]
        negative_indices = np.argsort(shap_values)

        top_positive = []
        for idx in positive_indices[:5]:
            if shap_values[idx] > 0:
                top_positive.append({
                    "feature": feature_names[idx],
                    "value": float(raw_features[idx]),
                    "shap_value": round(float(shap_values[idx]), 3),
                    "impact": round(abs(float(shap_values[idx])), 2),
                })

        top_negative = []
        for idx in negative_indices[:5]:
            if shap_values[idx] < 0:
                top_negative.append({
                    "feature": feature_names[idx],
                    "value": float(raw_features[idx]),
                    "shap_value": round(float(shap_values[idx]), 3),
                    "impact": round(abs(float(shap_values[idx])), 2),
                })

        prediction = expected + float(np.sum(shap_values))
        return {
            "expected_value": round(expected, 3),
            "prediction": round(prediction, 3),
            "fraud_probability": round(max(0.0, min(100.0, prediction * 100.0)), 2),
            "top_positive_features": top_positive,
            "top_negative_features": top_negative,
            "feature_importance": sorted(
                [{"feature": feature_names[i], "importance": round(abs(float(shap_values[i])), 3)}
                 for i in range(len(feature_names)) if abs(shap_values[i]) > 0.001],
                key=lambda x: x["importance"], reverse=True,
            )[:10],
        }

    def _fallback_explain(self, features: dict[str, float] | np.ndarray) -> dict[str, Any]:
        if isinstance(features, dict):
            items = sorted(features.items(), key=lambda x: abs(x[1]), reverse=True)
        else:
            items = [(self._feature_names[i], float(v)) for i, v in enumerate(features) if abs(v) > 0]
        top_pos = [{"feature": k, "value": v, "shap_value": round(v * 0.1, 3), "impact": round(abs(v) * 0.1, 2)}
                   for k, v in items[:5] if v > 0]
        top_neg = [{"feature": k, "value": v, "shap_value": round(v * 0.05, 3), "impact": round(abs(v) * 0.05, 2)}
                   for k, v in items[:3] if v < 0]
        return {
            "expected_value": 0.3, "prediction": 0.5,
            "fraud_probability": 50.0,
            "top_positive_features": top_pos,
            "top_negative_features": top_neg,
            "feature_importance": [{"feature": k, "importance": round(abs(v), 3)} for k, v in items[:10]],
        }
