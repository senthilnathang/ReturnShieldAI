# ReturnShield AI Architecture

## Overview

ReturnShield AI is a decisioning system for shipment return fraud. It covers the full pipeline: request ingestion, rule evaluation, multi-engine ML scoring, explainability, case review, feedback storage, and real-time async processing.

The system has two parallel architectures:
- **Hackathon MVP** — lightweight SQLite + SQLModel, single-process
- **Production Foundation** — PostgreSQL 15 + Redis 7 + SQLAlchemy 2.0 async, Docker Compose

## Architecture — Production Foundation

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client (REST API)                         │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│                     FastAPI (uvicorn, 4 workers)                  │
│                                                                   │
│  /api/v1/* routes:                                                │
│   health, imports, returns, fraud-cases, dashboard, customers     │
│                                                                   │
│  Services:                                                        │
│   ImportService → chunked CSV parsing + auto-mapping              │
│   ScoringStubService → 8 rule conditions                         │
│   DashboardService → cached aggregation                           │
│   CacheService → Redis TTL caching                                │
│   RealtimeService → Redis Streams + Pub/Sub                      │
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
│  16 tables   │  │   cache TTL  │  │ realtime_worker   │
│  + BRIN/GIN  │  │ • Scoring    │  │  (Redis Stream)   │
│  + full-text │  │   Stream     │  │                  │
│  + composite  │  │ • Pub/Sub    │  │ import_worker     │
│    indexes    │  │ • Rate limit │  │  (CLI-driven)    │
│              │  │ • Feature    │  │                  │
└──────────────┘  │   cache      │  └──────────────────┘
                  └──────────────┘
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
    │     ├── FraudScore created (rule_score + placeholder ML scores)
    │     └── FraudCase created (if score >= 40)
    │
    ├── Publish Pub/Sub events
    │     ├── fraud_cases:new
    │     └── fraud_scores:updated
    │
    └── ACK the stream entry
```

## Request Flow (Detailed)

1. Return request submitted via REST API
2. Backend stores customer, order, shipment, return request in PostgreSQL
3. Return is enqueued to Redis Stream for async scoring
4. Worker consumes the stream entry
5. Rule stub evaluates 8 conditions: return frequency, product value, weight mismatch, quick return, chargeback history, refund account reuse, suspicious text, new account
6. ML placeholders: structured_ml_score, nlp_score, graph_score, anomaly_score (to be filled by engine modules)
7. FraudScore record created with breakdown
8. FraudCase record created for score >= 40
9. Analyst reviews the case and submits feedback
10. Feedback is persisted for later retraining

## Database Schema (16 Tables)

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
  └── import_jobs / audit_events
```

Full 16-table listing: `merchants`, `customers`, `customer_identities`, `orders`, `shipments`, `return_requests`, `return_items`, `payments`, `refunds`, `support_interactions`, `fraud_scores`, `fraud_cases`, `rules`, `analyst_feedback`, `import_jobs`, `audit_events`

## Scoring Model

Fusion formula:
```
final_score =
  (rule_score * 0.30) +
  (structured_ml_score * 0.30) +
  (nlp_score * 0.25) +
  (anomaly_score * 0.15)
```

Decision mapping:
- `0-39` → `AUTO_APPROVE`
- `40-69` → `MANUAL_REVIEW`
- `70-100` → `HOLD_REFUND_HIGH_RISK`

## Component Map

### Backend API — Production
`/opt/ReturnShieldAI/backend/app/prod_main.py` (21 endpoints under `/api/v1`)

### Backend API — Hackathon
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
Five model families (same in both codebases):
- structured model: RandomForest on behavioral features
- NLP model: TF-IDF + cosine similarity
- anomaly model: IsolationForest on timing/value patterns
- graph features: NetworkX PageRank + Louvain communities
- fusion engine: weighted ensemble (30/30/25/15)

### 20 Modular Engines
`alert_engine`, `anomaly_engine`, `decision_engine`, `evidence_engine`, `feature_engine`, `fusion_engine`, `graph_engine`, `investigation_engine`, `kaggle_import`, `merchant_engine`, `monitoring_engine`, `nlp_engine`, `rule_engine`, `structured_ml`, `timeline_engine`, `vector_engine` (FAISS + Qdrant)

### Workers (Production only)
- `realtime_worker.py` — Redis Stream consumer, auto-scaling via consumer groups
- `import_worker.py` — CLI-driven CSV import with chunking

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
- PostgreSQL 15 + Redis 7 + Backend (4 workers)
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
- use simple model baselines that train quickly
- prefer JSON rules over a complex rule builder
- keep the frontend modular and responsive
- PostgreSQL + Redis for production; SQLite for local dev
- Alembic migrations for schema versioning
- Async everywhere for the production stack
- Background workers via Redis Streams for decoupled scoring

## Extensibility

The system leaves room for:
- stronger NLP embeddings (sentence-transformers)
- graph-based fraud analytics (NetworkX + PageRank)
- image verification (OCR + photo similarity)
- LLM investigation assistant
- model artifact persistence and versioning
- alerting and export workflows (Slack, email, webhook)
- authentication and role separation
- SHAP explainability integration
- Multi-tenancy with full merchant isolation
