# Test Cases

This document summarizes the current verification coverage for the production ML layer and the backend integration points.

## ML Feature Engineering

- `tests/test_ml_feature_store.py`
- Verifies derived fraud signals such as `has_empty_box_claim`, `has_urgent_refund_language`, `refund_to_order_value_ratio`, and `weight_difference`.

## Model Registry

- `tests/test_ml_registry.py`
- Verifies save/load round-trip, artifact persistence, and best-model promotion.

## Model Selection

- `tests/test_ml_selector.py`
- Verifies best-model ranking uses PR-AUC first, then F1, then lower false positive rate.

## Training Run Persistence

- `tests/test_ml_training_run_model.py`
- Verifies the `model_training_runs` table exists and accepts persisted training rows.

## Module Smoke Test

- `backend/app/modules/ml_engine/tests/test_smoke.py`
- Verifies the ML engine package imports and exposes the expected config surface.

## Recommended Commands

```bash
# ML unit tests
pytest tests/test_ml_feature_store.py tests/test_ml_registry.py tests/test_ml_selector.py backend/app/modules/ml_engine/tests/test_smoke.py -v

# DB-backed model-run persistence check
env TEST_DATABASE_URL=postgresql://girdersoft:girdersoft@localhost:5433/returnshield \
    TEST_DATABASE_URL_ASYNC=postgresql+asyncpg://girdersoft:girdersoft@localhost:5433/returnshield \
    pytest tests/test_ml_training_run_model.py -v

# Full ML verification set
env TEST_DATABASE_URL=postgresql://girdersoft:girdersoft@localhost:5433/returnshield \
    TEST_DATABASE_URL_ASYNC=postgresql+asyncpg://girdersoft:girdersoft@localhost:5433/returnshield \
    pytest tests/test_ml_feature_store.py tests/test_ml_registry.py tests/test_ml_selector.py tests/test_ml_training_run_model.py backend/app/modules/ml_engine/tests/test_smoke.py -v
```

## Current Status

- All five ML-focused tests pass in the current workspace.
- The DB-backed test confirms the new `model_training_runs` ORM model and migration path are wired correctly.
- The ML layer trains from PostgreSQL and falls back safely when no artifact exists.
