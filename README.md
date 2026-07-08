# ReturnShield AI

ReturnShield AI is a shipment return fraud decisioning platform for e-commerce and retail teams. It scores each return request, explains why it was flagged, and stores analyst feedback for follow-up review and retraining.

## Product Flow

`Return request -> normalization -> rules -> structured ML -> NLP -> anomaly detection -> fusion score -> case creation -> analyst decision -> feedback`

## What The System Does

- scores return requests from 0 to 100
- maps score bands to `AUTO_APPROVE`, `MANUAL_REVIEW`, or `HOLD_REFUND_HIGH_RISK`
- generates reason codes and a human explanation
- stores cases, analyst actions, and feedback labels
- exposes a rules page for simple JSON-backed business controls
- shows fraud ring, NLP, anomaly, and investigator signals in the UI

## Tech Stack

- Python 3.12
- FastAPI
- SQLModel / SQLAlchemy
- Pydantic
- scikit-learn
- React + TypeScript
- Vite
- Tailwind CSS
- SQLite for local development
- PostgreSQL for Docker Compose mode

## Project Layout

- `backend/` backend API, models, ML pipeline, and seed data
- `frontend/` analyst dashboard
- `run.sh` local install, run, restart, check, test, and load commands
- `docs/architecture.md` system architecture overview
- `docs/` supporting documentation

## Local Setup

### 1. Install dependencies

```bash
./run.sh install all
```

### 2. Load local seed data

```bash
./run.sh load demo local
```

This seeds the local SQLite database with sample customers, orders, returns, cases, rules, and feedback.

### 3. Start the app in dev mode

```bash
./run.sh run dev
```

Backend:
- `http://127.0.0.1:8000`

Frontend:
- `http://127.0.0.1:5173`

### 4. Validate the build

```bash
./run.sh check all
./run.sh test all
```

### 5. Manage services

```bash
./run.sh status
./run.sh restart all
./run.sh stop all
```

## `run.sh` Reference

### Install

```bash
./run.sh install backend
./run.sh install frontend
./run.sh install all
```

### Run

```bash
./run.sh run backend
./run.sh run frontend
./run.sh run all
./run.sh run dev
```

### Restart

```bash
./run.sh restart backend
./run.sh restart frontend
./run.sh restart all
./run.sh restart dev
```

### Check

```bash
./run.sh check backend
./run.sh check frontend
./run.sh check all
./run.sh check dev
```

### Test

```bash
./run.sh test backend
./run.sh test frontend
./run.sh test all
./run.sh test dev
```

### Load sample data

```bash
./run.sh load demo local
./run.sh load demo compose
```

### Status and logs

```bash
./run.sh status
./run.sh logs backend
./run.sh logs frontend
```

## API Reference

### Health

`GET /api/health`

### Return intake and scoring

`POST /api/returns`

Creates customer, order, return, case, and fraud score records, then returns the scoring result.

`POST /api/returns/score`

Scores a return payload without relying on the full intake flow.

Example request:

```json
{
  "customer": {
    "name": "Mia Patel",
    "email": "mia.patel@example.com",
    "phone": "+1-202-555-0199",
    "account_age_days": 21,
    "address": "88 Fraud Lane",
    "device_id": "device-fraud",
    "lifetime_orders": 9,
    "lifetime_returns": 6
  },
  "order": {
    "sku": "SKU-1002",
    "product_name": "Designer Jacket",
    "category": "apparel",
    "product_value": 420,
    "expected_weight": 0.8,
    "payment_method": "card",
    "payment_method_risk_score": 14,
    "delivery_date": "2026-07-08T09:00:00Z",
    "delivery_status": "delivered"
  },
  "return": {
    "return_reason": "Box arrived empty, request full refund.",
    "chat_transcript": "Customer insists the box was empty.",
    "email_text": "I want a refund immediately or I will open a chargeback.",
    "returned_weight": 0.1,
    "condition_reported": "empty_box"
  }
}
```

Example response fields:

```json
{
  "risk_score": 87.4,
  "risk_level": "HIGH",
  "decision": "HOLD_REFUND_HIGH_RISK",
  "recommended_action": "Hold refund and assign to senior fraud analyst",
  "score_breakdown": {
    "rule_score": 82,
    "structured_ml_score": 76,
    "nlp_score": 91,
    "anomaly_score": 68
  },
  "reason_codes": [
    "Weight mismatch detected",
    "Customer has 7 returns in last 30 days",
    "Return text similar to previous fraud cases",
    "High-value item returned within 12 hours"
  ]
}
```

### Cases

- `GET /api/cases`
- `GET /api/cases/{case_id}`
- `PATCH /api/cases/{case_id}/decision`

### Dashboard

- `GET /api/dashboard/metrics`

### Rules

- `GET /api/rules`
- `POST /api/rules`
- `PATCH /api/rules/{rule_id}`

### Model retraining

- `POST /api/ml/retrain`

## Data Model

Core tables:

- `customers`
- `orders`
- `returns`
- `return_cases`
- `fraud_scores`
- `rules`
- `analyst_feedback`
- `model_training_runs`

## Scoring Logic

Fusion formula:

```text
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

## UI Pages

- Overview dashboard
- Case queue
- Case detail and evidence panel
- Decision engine view
- AI / ML enhancements page
- Rules page
- Feedback page

## Screenshots

Add screenshots here if needed:

- `docs/screenshots/overview.png`
- `docs/screenshots/cases.png`
- `docs/screenshots/detail.png`
- `docs/screenshots/enhancements.png`

## Design Notes

- simple weighted fusion instead of a heavy orchestration engine
- explainable output instead of opaque risk numbers
- seeded synthetic data instead of requiring a historical fraud dataset
- analyst feedback stored for future retraining

## Next Improvements

- stronger embeddings for NLP similarity
- persisted model artifacts
- merchant-specific thresholds
- alerting and export workflows
- graph visualizations for fraud rings
- stronger evidence drill-down charts
