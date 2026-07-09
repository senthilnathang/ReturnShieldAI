# ReturnShield AI Architecture

## Overview

ReturnShield AI is a decisioning system for shipment-return fraud. It covers the full pipeline: request ingestion, rule evaluation, supervised ML scoring, explainability, case review, feedback storage, and real-time async processing.

The system has two parallel architectures:
- **Hackathon MVP** - SQLite + SQLModel
- **Production Foundation** - PostgreSQL 15 + Redis 7 + SQLAlchemy 2.0 async, Docker Compose

## Architecture - Production Foundation

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client (REST API)                         │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│                     FastAPI (uvicorn, workers)                   │
│                                                                   │
│  /api/v1/* routes:                                                │
│   health, imports, returns, fraud-cases, dashboard, customers,    │
│   orders, ml                                                     │
│                                                                   │
│  Services:                                                        │
│   ImportService -> chunked CSV parsing + auto-mapping            │
│   ScoringStubService -> rule-led supervised score with heuristic fallback                 │
│   ML engine -> train, register, predict, promote best model      │
│   DashboardService -> cached aggregation                          │
│   CacheService -> Redis TTL caching                               │
│   RealtimeService -> Redis Streams + Pub/Sub                     │
│                                                                   │
│  Repositories (SQLAlchemy 2.0 async):                             │
│   BaseRepository<T> generic CRUD                                  │
│   Customer, Order, Return, Fraud, Dashboard repositories          │
└──────────┬──────────────┬──────────────────┬─────────────────────┘
           │              │                  │
           ▼              ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
│  PostgreSQL   │  │    Redis 7   │  │  Background       │
│  15 (asyncpg) │  │              │  │  Workers          │
│              │  │ • Dashboard  │  │                  │
│  tables,    │  │   cache TTL   │  │ realtime_worker   │
│  indexes,    │  │ • Scoring    │  │  (Redis Stream)   │
│  training    │  │   Stream     │  │                  │
│  runs        │  │ • Pub/Sub    │  │ import_worker     │
│              │  │ • Rate limit  │  │  (CLI-driven)     │
│              │  │ • Feature     │  │ ml_training_worker│
│              │  │   cache       │  │  (Redis Stream)   │
└──────────────┘  └──────────────┘  └──────────────────┘
```

## Real-Time Scoring Flow

```
Return Created (POST /api/v1/returns)
    │
    ├── Persist to PostgreSQL (ReturnRequest, Customer, Order)
    │
    ├── Enqueue to Redis Stream (returns:score:stream)
    │
    ▼
realtime_worker (consumer group: scoring-workers)
    │
    ├── ScoringStubService.score_return()
    │     ├── 8 rule conditions evaluated
    │     ├── ML model called when artifact exists
    │     └── FraudScore created with final score breakdown
    │
    ├── Publish Pub/Sub events
    │     ├── fraud_cases:new
    │     └── fraud_scores:updated
    │
    └── ACK the stream entry
```

## ML Training Flow

```
Training request or worker job
    │
    ├── Load join-based feature set from PostgreSQL
    ├── Build preprocessing pipeline
    ├── Train Logistic Regression / Random Forest / XGBoost / Neural Net
    ├── Evaluate with accuracy, precision, recall, F1, ROC-AUC, PR-AUC
    ├── Choose best model by PR-AUC -> F1 -> false positive rate
    ├── Persist artifact + metadata + metrics under backend/models/
    ├── Register training run in PostgreSQL
    └── Promote best artifact into backend/models/best_model/
```

## Request Flow (Detailed)

1. Return request submitted via REST API
2. Backend stores customer, order, shipment, return request in PostgreSQL
3. Return is enqueued to Redis Stream for async scoring
4. Worker consumes the stream entry
5. Rule stub evaluates 8 conditions: return frequency, product value, weight mismatch, quick return, chargeback history, refund account reuse, suspicious text, new account
6. ML score is retrieved from the best available supervised model; if no artifact exists, the scorer uses a heuristic fallback and logs a warning
7. FraudScore record created with breakdown
8. FraudCase record created for score >= 40
9. Analyst reviews the case and submits feedback
10. Feedback is persisted for later retraining

## Database Schema (17 Tables)

```
merchants
  ├── customers ──┬── customer_identities (email, phone, address, device, IP)
  │               ├── orders ──┬── shipments (with weights)
  │               │            ├── return_items
  │               │            └── payments (with chargeback flag)
  │               ├── return_requests ──┬── return_items
  │               │                     ├── refunds (with account hash)
  │               │                     └── support_interactions (with sentiment)
  │               └── fraud_scores ──── fraud_cases (with status, priority)
  ├── rules (multi-version, condition_expression)
  ├── analyst_feedback (decision + confirmed_label)
  └── import_jobs / audit_events / model_training_runs
```

Full listing: `merchants`, `customers`, `customer_identities`, `orders`, `shipments`, `return_requests`, `return_items`, `payments`, `refunds`, `support_interactions`, `fraud_scores`, `fraud_cases`, `rules`, `analyst_feedback`, `import_jobs`, `audit_events`, `model_training_runs`

## Scoring Model

Current scoring formula:
```
final_score =
  (rule_score * 0.35) +
  (ml_score * 0.65)
```
Fallback: if no promoted model artifact exists, the scorer uses a heuristic path and logs a warning.

Decision mapping:
- `0-39` -> `AUTO_APPROVE`
- `40-69` -> `MANUAL_REVIEW`
- `70-100` -> `HOLD_REFUND_HIGH_RISK`

## ML Module Map

### Production ML Engine
`backend/app/modules/ml_engine/`
- data loader from PostgreSQL
- preprocessing + feature store
- model registry and artifact persistence
- prediction API and scoring fallback
- background training worker
- training comparison and model promotion

### Legacy ML Layer
The older `backend/app/ml/` modules remain in place for compatibility and future signal expansion.

## Component Map

### Backend API - Production
`/opt/ReturnShieldAI/backend/app/prod_main.py` (21 endpoints under `/api/v1`)

### Backend API - Hackathon
`/opt/ReturnShieldAI/backend/app/main.py` (12 endpoints under `/api/`)

### Database Layer
- **Production**: SQLAlchemy 2.0 async ORM, Alembic migrations, asyncpg driver
- **Hackathon**: SQLModel, SQLite via `run.sh`

### Redis Layer (Production only)
- Dashboard cache with TTL auto-expiry
- Scoring queue via Stream + Consumer Group
- Pub/Sub for real-time dashboard updates
- Rate limiting per merchant (Sorted Set)
- Feature cache for re-usable computations

### ML Layer
Model families in production:
- Logistic Regression
- Random Forest
- XGBoost
- Neural Network

### Workers (Production only)
- `realtime_worker.py` - Redis Stream consumer
- `import_worker.py` - CLI-driven CSV import with chunking
- `ml_training_worker.py` - async model retraining worker

### Frontend
React + TypeScript + Vite + Tailwind CSS
Pages: overview dashboard, case queue, case detail, decision engine, AI/ML signals, rules, feedback

## Deployment Modes

### Dev Mode (Hackathon)
```bash
./run.sh run dev
```
- Backend on port 8000 (SQLite)
- Frontend on port 5173

### Docker Compose (Production)
```bash
docker compose up
```
- PostgreSQL 15 + Redis 7 + Backend
- Auto-runs Alembic migrations on startup
- Persistent volumes for DB and Redis

### Local Production Dev (No Docker)
```bash
# Start PostgreSQL + Redis separately
cd backend && pip install -r requirements.txt
alembic upgrade head
python app/scripts/seed_demo_data.py
uvicorn app.prod_main:app --reload --port 8000
```

## Design Choices

- keep the decision engine explicit and inspectable
- store every score and explanation for auditability
- train multiple supervised models from PostgreSQL instead of relying on a single heuristic
- rank by PR-AUC first because fraud data is imbalanced
- prefer JSON rules over a complex rule builder
- keep the frontend modular and responsive
- PostgreSQL + Redis for production; SQLite for local dev
- Alembic migrations for schema versioning
- Async everywhere for the production stack
- Background workers via Redis Streams for decoupled scoring and retraining

## Extensibility

The system leaves room for:
- stronger NLP embeddings (sentence-transformers)
- graph-based fraud analytics (NetworkX + PageRank)
- image verification (OCR + photo similarity)
- LLM investigation assistant
- SHAP explainability integration
- Multi-tenancy with full merchant isolation
- model registry rollback and blue/green model promotion


## Business Logic Architecture

See [docs/business-logic-architecture.md](business-logic-architecture.md) and [docs/decisioning-architecture.md](decisioning-architecture.md) for the end-to-end flow from return request to model promotion.
