# ReturnShield AI FAQ

## What is ReturnShield AI?

A fraud decisioning platform purpose-built for e-commerce shipment returns. Two codebases coexist:
- **Hackathon MVP** — lightweight SQLite + SQLModel for local dev
- **Production Foundation** — PostgreSQL 15 + Redis 7 + FastAPI + SQLAlchemy 2.0 async, Docker Compose

## Is this a clone of Marble?

No. It is inspired by useful product ideas: decisioning, rules, scoring, explanation, and analyst review. The implementation is custom and intentionally smaller.

## How do I run the Hackathon MVP locally?

```bash
./run.sh install all
./run.sh run dev
```

## How do I run the Production Foundation?

```bash
docker compose up -d postgres redis
cd backend && pip install -r requirements.txt
alembic upgrade head
python app/scripts/seed_demo_data.py
uvicorn app.prod_main:app --reload --port 8000
```

## How do I import a Kaggle dataset?

```bash
python app/scripts/import_kaggle_dataset.py \
    --file data/kaggle_returns.csv \
    --source kaggle \
    --chunk-size 10000
```

Auto-maps 28+ column aliases, creates customers/orders/shipments/returns/identities, tracks progress in `import_jobs` table.

## How do I reset the demo data?

```bash
./run.sh load demo          # Hackathon MVP
python app/scripts/seed_demo_data.py  # Production
```

## What ports are used?

- Backend: `8000` (hackathon) / `8000` (production)
- Frontend: `5173`
- PostgreSQL: `5432`
- Redis: `6379`

## What database does the system use?

- Hackathon MVP: SQLite (`backend/returnshield.db`)
- Production Foundation: PostgreSQL 15+ (async via asyncpg)

## What is the scoring logic?

A weighted fusion:
- rules (30%)
- structured ML (30%)
- NLP (25%)
- anomaly detection (15%)

## How are cases explained?

Every case includes:
- final risk score (0–100)
- decision bucket (AUTO_APPROVE / MANUAL_REVIEW / HOLD_REFUND_HIGH_RISK)
- recommended action
- score breakdown (rule, structured_ml, nlp, anomaly, graph)
- reason codes
- decision trace
- explainability panel

## Can analysts give feedback?

Yes. Analyst actions are stored in the database and can be used later for retraining.

## How does real-time scoring work?

Returns are scored asynchronously via Redis Streams. A background worker consumes the stream, runs the scoring stub, persists the result, and publishes events via Redis Pub/Sub.

## What are the 16 production tables?

`merchants`, `customers`, `customer_identities`, `orders`, `shipments`, `return_requests`, `return_items`, `payments`, `refunds`, `support_interactions`, `fraud_scores`, `fraud_cases`, `rules`, `analyst_feedback`, `import_jobs`, `audit_events`

## How do I run the tests?

```bash
pytest tests/ -v --cov=app
```

Requires a PostgreSQL `returnshield_test` database.
