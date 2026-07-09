# ReturnShield AI - Developer Guide

## Architecture Overview

Two codebases coexist in the same repository:

| Aspect | Hackathon MVP | Production Foundation |
|--------|--------------|----------------------|
| Entry point | `backend/app/main.py` | `backend/app/prod_main.py` |
| API routes | `backend/app/api.py` | `backend/app/api_v1/` |
| Models | `backend/app/models/` (SQLModel, 8 tables) | `backend/app/prod_models/` (SQLAlchemy 2.0, 17 tables) |
| Database | SQLite | PostgreSQL 15+ |
| Cache | None | Redis 7 |
| Workers | None | Redis Stream consumer + CLI import + ML training worker |

## Project Layout

```
backend/
├── app/
│   ├── main.py                   # Hackathon entry: uvicorn backend.app.main:app
│   ├── prod_main.py              # Production entry: uvicorn app.prod_main:app
│   ├── api.py                    # Hackathon API routes
│   ├── api_v1/                   # Production API routes, including /ml
│   ├── models/                   # Hackathon SQLModel entities
│   ├── prod_models/              # Production SQLAlchemy 2.0 models
│   ├── core/
│   │   ├── config.py             # Settings (DB URL, Redis URL, thresholds, CORS)
│   │   ├── database.py           # Async engine + session factories
│   │   ├── redis.py              # RedisClient wrapper (cache, streams, pub/sub, rate limit)
│   │   └── logging.py            # Structured logging setup
│   ├── db/
│   │   ├── base.py               # SQLAlchemy Base with UUID PK + created_at
│   │   └── session.py            # (Hackathon) SQLModel session
│   ├── repositories/             # Generic CRUD + specialized repos
│   ├── services/
│   │   ├── import_service.py     # Chunked CSV import with auto-mapping
│   │   ├── scoring_stub_service.py # Rule scoring plus ML fallback
│   │   ├── dashboard_service.py   # Cached dashboard aggregation
│   │   ├── cache_service.py       # Redis TTL cache wrapper
│   │   └── realtime_service.py    # Redis Stream + Pub/Sub helper
│   ├── scripts/
│   │   ├── seed_demo_data.py      # Demo merchant + customers + returns
│   │   ├── import_kaggle_dataset.py # Bulk CSV import
│   │   └── create_indexes.py      # Advanced database indexes
│   ├── workers/
│   │   ├── realtime_worker.py     # Redis Stream consumer daemon
│   │   ├── import_worker.py       # CLI-driven CSV import
│   │   └── ml_training_worker.py   # Async model retraining worker
│   ├── ml/                        # Legacy ML model families and fusion engine
│   ├── modules/                   # Production engine modules, including ml_engine
│   └── rules/                     # Rule engine + default rules
├── alembic/                       # Schema migrations
└── tests/                         # Pytest test suite
```

## Setting Up the Development Environment

### Prerequisites
- Python 3.11+
- PostgreSQL 15+ (for production)
- Redis 7+ (for production)
- Node.js 18+ and npm (for frontend)

### Production Stack Setup

```bash
# 1. Start databases
docker compose up -d postgres redis

# 2. Install Python dependencies
cd backend
pip install -r requirements.txt

# 3. Run migrations
alembic upgrade head

# 4. Seed demo data
python app/scripts/seed_demo_data.py

# 5. Start the API
uvicorn app.prod_main:app --reload --port 8000

# 6. Start the scoring worker (separate terminal)
python -m app.workers.realtime_worker --consumer worker-1

# 7. Train the supervised ML models
python -m backend.app.modules.ml_engine.train_all
```

### Running Tests

```bash
# Root test suite, including ML tests and DB-backed checks
pytest tests/ -v

# Run specific ML tests
pytest tests/test_ml_feature_store.py tests/test_ml_registry.py tests/test_ml_selector.py tests/test_ml_training_run_model.py -v

# Run with coverage report
pytest tests/ --cov=app --cov-report=html
```

## Adding a New API Endpoint

1. Add route handler in `backend/app/api_v1/<resource>.py`
2. Add Pydantic schema in `backend/app/modules/ml_engine/schemas.py` or `backend/app/schemas/`
3. Add repository method in `backend/app/repositories/`
4. Add service method in `backend/app/services/` (if needed)
5. Register the router in `backend/app/api_v1/__init__.py`

## Adding a New Database Table

1. Create model in `backend/app/prod_models/<name>.py`
2. Import and export in `backend/app/prod_models/__init__.py`
3. Generate migration: `alembic revision --autogenerate -m "description"`
4. Review and edit the migration file
5. Run: `alembic upgrade head`

## Adding a New Scoring Rule

Edit `ScoringStubService.score_return()` in `backend/app/services/scoring_stub_service.py`.
Each rule adds a condition check that contributes to the `rule_score`.
If the supervised model is unavailable, the scorer falls back to a warning-logged heuristic and still returns a response.

## Adding a New ML Model

1. Add a training script in `backend/app/modules/ml_engine/`
2. Extend `MODEL_TYPES` in `train_all.py`
3. Update the model registry metadata and selection logic if needed
4. Add a test in `tests/`
5. Persist artifacts to `backend/models/<model_type>/<version>/`

## Import Pipeline

The import system (`ImportService`) auto-detects column mappings from 28+ known aliases.

To add a new mapping, extend `COLUMN_MAP` in `import_service.py`.

## Redis Client API

```python
from app.core.redis import redis_client

await redis_client.initialize()

# Cache
await redis_client.cache_set("key", data, ttl=300)
data = await redis_client.cache_get("key")

# Streams
await redis_client.stream_add("returns:score:stream", {"return_id": str(id)})
messages = await redis_client.stream_read("returns:score:stream", group="scoring-workers", consumer="worker-1")

# Pub/Sub
await redis_client.publish("fraud_cases:new", {"case_id": str(id)})

# Rate limiting
allowed = await redis_client.rate_limit_check("merchant:{id}:score_api", max_requests=100, window_seconds=60)
```

## Docker Compose

```bash
# Full stack
docker compose up --build

# Individual services
docker compose up -d postgres redis
docker compose up backend

# View logs
docker compose logs -f backend
```

## Performance Targets

| Operation | Target |
|-----------|--------|
| Return creation API | < 300ms |
| Scoring enqueue | < 100ms |
| Stub scoring | < 1s |
| Dashboard (cached) | < 500ms |
| Paginated case list | < 1s |
| 1M record import | < 30 min |
