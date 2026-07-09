# ReturnShield AI

ReturnShield AI is a shipment return fraud decisioning platform for e-commerce and retail teams. It scores each return request, explains why it was flagged, and stores analyst feedback for follow-up review and retraining.

The project has two parallel codebases:
- **Hackathon MVP** — lightweight system using SQLModel + SQLite, runs locally via `run.sh`
- **Production Foundation** — PostgreSQL 15 + Redis 7 + FastAPI + SQLAlchemy 2.0 async, runs via Docker Compose

## Product Flow

```
Return request → normalization → rules → structured ML → NLP → anomaly detection → graph features → fusion score → case creation → analyst decision → feedback
```

## What The System Does

- scores return requests from 0 to 100
- maps score bands to `AUTO_APPROVE`, `MANUAL_REVIEW`, or `HOLD_REFUND_HIGH_RISK`
- generates reason codes and a human explanation
- stores cases, analyst actions, and feedback labels
- exposes a rules page for simple JSON-backed business controls
- shows fraud ring, NLP, anomaly, and investigator signals in the UI

## Tech Stack

| Layer | Hackathon MVP | Production Foundation |
|-------|--------------|----------------------|
| **Backend** | FastAPI + SQLModel | FastAPI + SQLAlchemy 2.0 async |
| **Database** | SQLite (file) | PostgreSQL 15+ (async via asyncpg) |
| **Cache/Queue** | — | Redis 7+ (streams, pub/sub, cache) |
| **ML** | scikit-learn (5 families) | Same + Pandas (import pipeline) |
| **Migrations** | — | Alembic |
| **Frontend** | React + TypeScript + Vite + Tailwind CSS | Same |
| **Deployment** | `run.sh` dev mode | Docker Compose (3 services) |
| **Workers** | — | Redis Stream consumer + CLI import worker |

## Project Layout

```
├── backend/                  # Backend API, models, ML pipeline, seed data
│   ├── app/
│   │   ├── main.py           # Hackathon MVP entry point
│   │   ├── prod_main.py      # Production Foundation entry point
│   │   ├── api.py            # Hackathon MVP API routes
│   │   ├── api_v1/           # Production API v1 routes (21 endpoints)
│   │   ├── models/           # Hackathon MVP SQLModel entities (8 tables)
│   │   ├── prod_models/      # Production SQLAlchemy models (16 tables)
│   │   ├── core/             # Config, database, redis, logging
│   │   ├── db/               # Base, session, migrations
│   │   ├── ml/               # ML pipeline (5 families)
│   │   ├── modules/          # 20 production engine modules
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
├── docs/                     # Documentation
├── sample_data/              # Synthetic demo corpus
├── docker-compose.yml        # Production stack
├── pitch_deck_data.md        # Investor pitch content
├── pitch_deck.html           # Interactive slides
└── pitch_deck_returnshield.pdf
```

## Quick Start — Hackathon MVP

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

## Quick Start — Production Foundation

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
| POST | `/returns/{return_id}/score-stub` | Score synchronously (stub) |

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

## Database Schema

### Hackathon MVP (8 tables)
`customers`, `orders`, `returns`, `return_cases`, `fraud_scores`, `rules`, `analyst_feedback`, `model_training_runs`

### Production Foundation (16 tables)

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
            └── import_jobs / audit_events
```

## Scoring Logic

Fusion formula:
```
final_score =
  (rule_score * 0.30)
+ (structured_ml_score * 0.30)
+ (nlp_score * 0.25)
+ (anomaly_score * 0.15)
```

Decision bands:
- `0-39` = `AUTO_APPROVE`
- `40-69` = `MANUAL_REVIEW`
- `70-100` = `HOLD_REFUND_HIGH_RISK`

## Real-Time Scoring Flow (Production)

```
Return Created → PostgreSQL → Redis Stream → Worker consumes →
    Scoring Stub → FraudScore + FraudCase created →
    Redis Pub/Sub → Dashboard refreshes
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

- `backend/app/ml/feature_engineering.py`
- `backend/app/ml/structured_model.py`
- `backend/app/ml/nlp_model.py`
- `backend/app/ml/anomaly_model.py`
- `backend/app/ml/fusion_engine.py`
- `backend/app/ml/explainability.py`
- `backend/app/ml/train.py`
- `backend/app/ml/sample_data_generator.py`
- `backend/app/ml/advanced_signals.py`
- `backend/app/ml/graph_features.py`

## 20 Production Engine Modules

`alert_engine`, `anomaly_engine`, `decision_engine`, `evidence_engine`, `feature_engine`, `fusion_engine`, `graph_engine`, `investigation_engine`, `kaggle_import`, `merchant_engine`, `monitoring_engine`, `nlp_engine`, `rule_engine`, `structured_ml`, `timeline_engine`, `vector_engine` (FAISS + Qdrant)

## UI Pages

- Overview dashboard (with cached metrics)
- Case queue (paginated, filterable)
- Case detail and evidence panel
- Decision engine view
- AI / ML enhancements page
- Rules page
- Feedback page

## Design Notes

- simple weighted fusion instead of a heavy orchestration engine
- explainable output instead of opaque risk numbers
- seeded synthetic data instead of requiring a historical fraud dataset
- analyst feedback stored for future retraining
- PostgreSQL + Redis for production; SQLite for local dev
- Alembic migrations for schema versioning
- Real-time scoring via Redis Stream consumer groups
- Background workers for CSV import and async scoring

## Next Improvements

- stronger NLP embeddings (sentence-transformers)
- persisted model artifacts with versioning
- merchant-specific thresholds
- alerting and export workflows (Slack, email, webhook)
- graph visualizations for fraud rings
- stronger evidence drill-down charts
- LLM investigation assistant
- image verification (OCR + photo similarity)
- SHAP explainability integration
- Multi-tenancy with full isolation
