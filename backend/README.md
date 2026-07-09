# ReturnShield AI - Production Foundation

AI-powered shipment-return fraud detection platform. PostgreSQL + Redis + FastAPI.

## Stack

- **Python 3.11+** / **FastAPI**
- **PostgreSQL 15+** (async via asyncpg)
- **Redis 7+** (streams, pub/sub, cache, rate limiting)
- **SQLAlchemy 2.0** (async ORM)
- **Alembic** (migrations)
- **Pandas** (CSV import with chunking)
- **scikit-learn / XGBoost / PyTorch** for supervised fraud models
- **Docker Compose**

## Quick Start

```bash
# 1. Start infrastructure
docker compose up -d postgres redis

# 2. Install dependencies
cd backend
pip install -r requirements.txt

# 3. Run migrations
alembic upgrade head

# 4. Seed demo data
python app/scripts/seed_demo_data.py

# 5. Start the API
uvicorn app.prod_main:app --reload --port 8000

# 6. Open docs
open http://localhost:8000/docs
```

## Import a Kaggle Dataset

```bash
# Download a Kaggle CSV, then:
python app/scripts/import_kaggle_dataset.py     --file data/kaggle_returns.csv     --source kaggle     --chunk-size 10000
```

This auto-maps columns, creates customers/orders/shipments/returns/identities,
and tracks progress in the `import_jobs` table.

## Fraud ML Engine

The production ML layer lives in `backend/app/modules/ml_engine/` and trains on PostgreSQL data.

### Supported models
- Logistic Regression
- Random Forest
- XGBoost
- Neural Network

### Training and registry commands
```bash
python -m backend.app.modules.ml_engine.train_all
python -m backend.app.modules.ml_engine.train_xgboost
python -m backend.app.modules.ml_engine.train_random_forest
python -m backend.app.modules.ml_engine.train_logistic_regression
python -m backend.app.modules.ml_engine.train_neural_network
```

### Model selection
- Primary: PR-AUC
- Secondary: F1
- Tiebreaker: lower false positive rate

### Artifact locations
- `backend/models/<model_type>/<version>/`
- `backend/models/best_model/`

### Prediction API
```bash
curl -X POST http://localhost:8000/api/v1/ml/predict   -H "Content-Type: application/json"   -d '{"return_id":"<UUID>"}'
```

## API Endpoints

All endpoints under `/api/v1`.

### Health
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Overall health |
| GET | `/health/postgres` | PostgreSQL connectivity |
| GET | `/health/redis` | Redis connectivity |

### Imports
| Method | Path | Description |
|--------|------|-------------|
| POST | `/imports/kaggle` | Start a CSV import job |
| GET | `/imports/{job_id}` | Get import job status |
| GET | `/imports` | List import jobs |

### Returns
| Method | Path | Description |
|--------|------|-------------|
| POST | `/returns` | Create a return request |
| GET | `/returns` | List returns (paginated) |
| GET | `/returns/{return_id}` | Get return details |
| POST | `/returns/{return_id}/enqueue-score` | Enqueue for async scoring |
| POST | `/returns/{return_id}/score-stub` | Score synchronously with fallback ML+rules |

### Fraud Cases
| Method | Path | Description |
|--------|------|-------------|
| GET | `/fraud-cases` | List fraud cases |
| GET | `/fraud-cases/{case_id}` | Get case details |
| PATCH | `/fraud-cases/{case_id}/status` | Update case status |

### Dashboard
| Method | Path | Description |
|--------|------|-------------|
| GET | `/dashboard/overview` | Dashboard metrics (cached) |
| GET | `/dashboard/risk-distribution` | Score distribution (cached) |
| GET | `/dashboard/recent-cases` | Recent high-risk cases |
| POST | `/dashboard/refresh-cache` | Invalidate Redis cache |

### ML Engine
| Method | Path | Description |
|--------|------|-------------|
| POST | `/ml/predict` | Predict fraud probability for a return |
| POST | `/ml/predict/batch` | Predict fraud probability for many returns |
| POST | `/ml/train` | Train and compare all supervised models |
| GET | `/ml/models` | List trained model artifacts |
| GET | `/ml/models/best` | Show the best promoted model |
| GET | `/ml/training-runs` | List training history from PostgreSQL |
| POST | `/ml/models/{model_type}/{version}/promote` | Promote an artifact to best |

## Redis Architecture

| Feature | Pattern | Keys |
|---------|---------|------|
| Dashboard cache | Key-Value with TTL | `dashboard:merchant:{id}:overview` |
| Scoring queue | Stream + Consumer Group | `returns:score:stream` |
| Live events | Pub/Sub | `fraud_cases:new`, `fraud_scores:updated` |
| Rate limiting | Sorted Set | `rate_limit:merchant:{id}:score_api` |
| Feature cache | Key-Value | `features:customer:{id}:return_stats` |

## Real-Time Scoring Flow

```
Return Created -> PostgreSQL -> Redis Stream -> Worker consumes ->
           Scoring Stub -> FraudScore + FraudCase created ->
           Redis Pub/Sub -> Dashboard refreshes
```

## Workers

```bash
# Realtime scoring worker (consumes Redis Stream)
python -m app.workers.realtime_worker --consumer worker-1

# Background import worker
python -m app.workers.import_worker --file data/large.csv --merchant-id <UUID>
```

## Tests

```bash
pytest tests/ -v --cov=app
```

## Database Schema (17 Tables)

`merchants`, `customers`, `customer_identities`, `orders`, `shipments`,
`return_requests`, `return_items`, `payments`, `refunds`,
`support_interactions`, `fraud_scores`, `fraud_cases`, `rules`,
`analyst_feedback`, `import_jobs`, `audit_events`, `model_training_runs`

## Performance Targets

| Operation | Target |
|-----------|--------|
| Return creation API | < 300ms |
| Scoring enqueue | < 100ms |
| Stub scoring | < 1s |
| Dashboard (cached) | < 500ms |
| Paginated case list | < 1s |
| 1M record import | < 30 min |
