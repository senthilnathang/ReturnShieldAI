# ReturnShield AI

ReturnShield AI is a shipment return fraud decisioning platform for e-commerce and retail teams. It scores each return request, explains why it was flagged, trains supervised fraud models from PostgreSQL data, and stores analyst feedback for follow-up review and retraining.

The project has two parallel codebases:
- **Hackathon MVP** - lightweight system using SQLModel + SQLite, runs locally via `run.sh`
- **Production Foundation** - PostgreSQL 15 + Redis 7 + FastAPI + SQLAlchemy 2.0 async, runs via Docker Compose

## Product Flow

```
Return request -> normalization -> rules -> supervised ML -> NLP -> anomaly detection -> graph features -> fusion score -> case creation -> analyst decision -> feedback
```

## What The System Does

- scores return requests from 0 to 100
- maps score bands to `AUTO_APPROVE`, `MANUAL_REVIEW`, or `HOLD_REFUND_HIGH_RISK`
- generates reason codes and a human explanation
- stores cases, analyst actions, and feedback labels
- exposes a rules page for simple JSON-backed business controls
- shows fraud ring, NLP, anomaly, investigator, and ML model signals in the UI

## Tech Stack

| Layer | Hackathon MVP | Production Foundation |
|-------|--------------|----------------------|
| **Backend** | FastAPI + SQLModel | FastAPI + SQLAlchemy 2.0 async |
| **Database** | SQLite (file) | PostgreSQL 15+ (async via asyncpg) |
| **Cache/Queue** | - | Redis 7+ (streams, pub/sub, cache) |
| **ML** | scikit-learn (5 families) | Logistic Regression, Random Forest, XGBoost, Neural Net, Pandas |
| **Migrations** | - | Alembic |
| **Frontend** | React + TypeScript + Vite + Tailwind CSS | Same |
| **Deployment** | `run.sh` dev mode | Docker Compose (3 services) |
| **Workers** | - | Redis Stream consumer + CLI import worker |

## Project Layout

```
├── backend/                  # Backend API, models, ML pipeline, seed data
│   ├── app/
│   │   ├── main.py           # Hackathon MVP entry point
│   │   ├── prod_main.py      # Production Foundation entry point
│   │   ├── api.py            # Hackathon MVP API routes
│   │   ├── api_v1/           # Production API v1 routes
│   │   ├── models/           # Hackathon MVP SQLModel entities
│   │   ├── prod_models/      # Production SQLAlchemy models (17 tables)
│   │   ├── core/             # Config, database, redis, logging
│   │   ├── db/               # Base, session, migrations
│   │   ├── ml/               # Legacy ML pipeline
│   │   ├── modules/          # Production engine modules, including ml_engine
│   │   ├── repositories/     # Data access layer
│   │   ├── schemas/          # Pydantic v2 schemas
│   │   ├── services/         # Business logic services
│   │   ├── rules/            # Rule engine
│   │   ├── scripts/          # Import, seed, index scripts
│   │   └── workers/          # Background workers
│   ├── alembic/              # Database migrations
│   ├── Dockerfile
│   └── README.md
├── frontend/                 # React analyst dashboard
├── docs/                     # Documentation and presentation assets
├── sample_data/              # Synthetic demo corpus
├── docker-compose.yml        # Production stack
├── pitch_deck_data.md        # Investor pitch content
├── pitch_deck.html           # Interactive slides
└── pitch_deck_returnshield.pdf
```

## Quick Start - Hackathon MVP

### 1. Install dependencies
```bash
./run.sh install all
```

### 2. Load local seed data
```bash
./run.sh load demo local
```

### 3. Start the app in dev mode
```bash
./run.sh run dev
```
- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:5173`

### 4. Validate
```bash
./run.sh check all
./run.sh test all
```

## Quick Start - Production Foundation

### 1. Start infrastructure
```bash
docker compose up -d postgres redis
```

### 2. Install dependencies
```bash
cd backend && pip install -r requirements.txt
```

### 3. Run migrations
```bash
alembic upgrade head
```

### 4. Seed demo data
```bash
python app/scripts/seed_demo_data.py
```

### 5. Start the API
```bash
uvicorn app.prod_main:app --reload --port 8000
```

Open `http://localhost:8000/docs`

## API Reference

### Hackathon MVP Endpoints (`/api/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/returns` | Create return + score |
| POST | `/returns/score` | Score payload only |
| GET | `/cases` | List cases (paginated, filtered) |
| GET | `/cases/{id}` | Case detail |
| PATCH | `/cases/{id}/decision` | Analyst decision |
| GET | `/dashboard/metrics` | Dashboard overview |
| GET | `/rules` | List rules |
| POST | `/rules` | Create rule |
| PATCH | `/rules/{id}` | Update rule |
| POST | `/ml/retrain` | Retrain models |
| POST | `/seed` | Seed demo data |

### Production Foundation Endpoints (`/api/v1/`)

#### Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Overall health |
| GET | `/health/postgres` | PostgreSQL connectivity |
| GET | `/health/redis` | Redis connectivity |

#### Imports
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/imports/kaggle` | Start CSV import job |
| GET | `/imports/{job_id}` | Import job status |
| GET | `/imports` | List import jobs |

#### Returns
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/returns` | Create return request |
| GET | `/returns` | List returns (paginated) |
| GET | `/returns/{return_id}` | Return details |
| POST | `/returns/{return_id}/enqueue-score` | Enqueue async scoring |
| POST | `/returns/{return_id}/score-stub` | Score synchronously with fallback rule+ML scoring |

#### Fraud Cases
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/fraud-cases` | List fraud cases |
| GET | `/fraud-cases/{case_id}` | Case details |
| PATCH | `/fraud-cases/{case_id}/status` | Update case status |

#### Dashboard
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/dashboard/overview` | Dashboard metrics (cached) |
| GET | `/dashboard/risk-distribution` | Score distribution (cached) |
| GET | `/dashboard/recent-cases` | Recent high-risk cases |
| POST | `/dashboard/refresh-cache` | Invalidate Redis cache |

#### Customers / Orders
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/customers/{customer_id}` | Customer detail |
| GET | `/orders/{order_id}` | Order detail |
| GET | `/orders` | List orders |

#### ML Engine
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/ml/predict` | Predict fraud probability for a return |
| POST | `/ml/predict/batch` | Predict fraud probability for many returns |
| POST | `/ml/train` | Train and compare supervised models |
| GET | `/ml/models` | List trained model artifacts |
| GET | `/ml/models/best` | Show the best promoted model |
| GET | `/ml/training-runs` | List training history from PostgreSQL |
| POST | `/ml/models/{model_type}/{version}/promote` | Promote an artifact to best |

## Database Schema

### Hackathon MVP (8 tables)
`customers`, `orders`, `returns`, `return_cases`, `fraud_scores`, `rules`, `analyst_feedback`, `model_training_runs`

### Production Foundation (17 tables)

```
merchants ──┬── customers ──┬── customer_identities
            │               ├── orders ──┬── shipments
            │               │            ├── return_items
            │               │            └── payments
            │               ├── return_requests ──┬── return_items
            │               │                     ├── refunds
            │               │                     └── support_interactions
            │               └── fraud_scores ──── fraud_cases
            ├── rules
            ├── analyst_feedback
            └── import_jobs / audit_events / model_training_runs
```

## Scoring Logic

Fusion formula:
```
final_score =
  (rule_score * 0.35)
+ (structured_ml_score * 0.65)
```

When the promoted supervised model exists, the production scorer uses it; otherwise it falls back to the rule stub and still returns a complete API response.

## ML Training

- Train and compare multiple supervised models from PostgreSQL
- Algorithms: Logistic Regression, Random Forest, XGBoost, Neural Network
- Rank by PR-AUC first, then F1, then false positive rate
- Persist artifacts under `backend/models/`
- Promote the best model automatically into `backend/models/best_model/`
- Expose prediction, training, registry, and promotion APIs under `/api/v1/ml`

Decision bands:
- `0-39` = `AUTO_APPROVE`
- `40-69` = `MANUAL_REVIEW`
- `70-100` = `HOLD_REFUND_HIGH_RISK`

## Real-Time Scoring Flow (Production)

```
Return Created -> PostgreSQL -> Redis Stream -> Worker consumes ->
    Scoring Stub -> FraudScore + FraudCase created ->
    Redis Pub/Sub -> Dashboard refreshes
```

### Redis Architecture
| Feature | Pattern |
|---------|---------|
| Dashboard cache | Key-Value with TTL |
| Scoring queue | Stream + Consumer Group |
| Live events | Pub/Sub channels |
| Rate limiting | Sorted Set |
| Feature cache | Key-Value |

## ML Modules

- `backend/app/modules/ml_engine/`
- `backend/app/ml/feature_engineering.py`
- `backend/app/ml/structured_model.py`
- `backend/app/ml/nlp_model.py`
- `backend/app/ml/anomaly_model.py`
- `backend/app/ml/fusion_engine.py`
- `backend/app/ml/explainability.py`
- `backend/app/ml/train.py`
- `backend/app/ml/sample_data_generator.py`
