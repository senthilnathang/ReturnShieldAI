from __future__ import annotations

from backend.app.modules.ml_engine.trainer_common import select_best_model


def test_select_best_model_uses_pr_auc_then_f1_then_fpr():
    rows = [
        {"model_type": "a", "version": "1", "pr_auc": 0.8, "f1": 0.7, "false_positive_rate": 0.2, "artifact_path": "/a"},
        {"model_type": "b", "version": "1", "pr_auc": 0.82, "f1": 0.6, "false_positive_rate": 0.3, "artifact_path": "/b"},
        {"model_type": "c", "version": "1", "pr_auc": 0.82, "f1": 0.75, "false_positive_rate": 0.25, "artifact_path": "/c"},
    ]
    best = select_best_model(rows)
    assert best["model_type"] == "c"
