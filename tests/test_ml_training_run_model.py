from __future__ import annotations

import pytest

from backend.app.prod_models.model_training_run import ModelTrainingRun


@pytest.mark.asyncio
async def test_model_training_run_table_persists(db_session):
    run = ModelTrainingRun(
        model_name="logistic_regression",
        model_type="logistic_regression",
        version="2026-07-09-001",
        accuracy=0.9,
        precision=0.8,
        recall=0.7,
        f1=0.75,
        roc_auc=0.88,
        pr_auc=0.82,
        false_positive_rate=0.1,
        false_negative_rate=0.2,
        training_time_seconds=1.2,
        prediction_latency_ms=10.0,
        artifact_path="/tmp/model.pkl",
        metrics_json={"pr_auc": 0.82},
        metadata_json={"feature_columns": ["product_value"]},
    )
    db_session.add(run)
    await db_session.flush()
    assert run.id is not None
