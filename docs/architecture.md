# ReturnShield AI Architecture

## Overview

ReturnShield AI is a small decisioning system for shipment return fraud. It keeps the useful parts of a fraud platform: request ingestion, rule evaluation, scoring, explainability, case review, and feedback storage.

## High-Level Flow

```text
Return request
  -> normalize data
  -> build structured features
  -> evaluate rules
  -> score with structured ML
  -> score text with NLP
  -> score anomalies
  -> optionally compute graph / ring features
  -> fuse signals into one risk score
  -> create case and explanation
  -> analyst reviews case
  -> feedback is stored for retraining
```

## Component Map

### Backend API

FastAPI exposes the public endpoints for scoring, case management, rules, dashboard metrics, and retraining.

Important responsibilities:

- accept return payloads
- persist customer, order, return, case, and fraud score records
- evaluate rules and model outputs
- store analyst decisions and feedback
- seed demo data for local use

### Database

SQLModel and SQLAlchemy back the persistence layer.

Core entities:

- `customers`
- `orders`
- `returns`
- `return_cases`
- `fraud_scores`
- `rules`
- `analyst_feedback`
- `model_training_runs`

### ML Layer

The ML layer is intentionally lightweight and modular.

- structured model: behavioral fraud patterns from return history and shipment attributes
- NLP model: fraud-language and repeated-script detection
- anomaly model: unusual combinations and timing patterns
- fusion engine: weighted score composition
- explainability: reason codes and analyst-readable summaries
- advanced signals: graph fraud, image/OCR, and investigator summaries

### Frontend

The React dashboard supports the analyst workflow.

Primary pages:

- overview dashboard
- case queue
- case detail
- decision engine
- AI / ML signals
- rules management
- feedback review

## Request Flow

1. A return request is submitted through the API or UI.
2. Backend stores the customer, order, and return payload.
3. Rule engine checks JSON-configurable conditions.
4. Structured ML scores behavioral risk.
5. NLP scores return reason, chat, and email text.
6. Anomaly model flags unusual combinations.
7. Optional graph features identify connected fraud rings.
8. Fusion engine combines all signals into a final score.
9. Decision engine maps the score to a case outcome.
10. Analyst reviews the case and submits feedback.
11. Feedback is persisted for later retraining.

## Scoring Model

Fusion formula:

```text
final_score =
  (rule_score * 0.30)
+ (structured_ml_score * 0.30)
+ (nlp_score * 0.25)
+ (anomaly_score * 0.15)
```

Decision mapping:

- `0-39` -> `AUTO_APPROVE`
- `40-69` -> `MANUAL_REVIEW`
- `70-100` -> `HOLD_REFUND_HIGH_RISK`

## Local Runtime Modes

### Dev Mode

- backend: `./run.sh run backend`
- frontend: `./run.sh run frontend`
- combined: `./run.sh run dev`
- DB: local SQLite file managed by `run.sh`

### Compose Mode

- `./run.sh compose up`
- backend container
- frontend container
- PostgreSQL container

## Design Choices

- keep the decision engine explicit and inspectable
- store every score and explanation for auditability
- use simple model baselines that train quickly
- prefer JSON rules over a complex rule builder
- keep the frontend modular and responsive

## Extensibility

The system leaves room for:

- stronger NLP embeddings
- graph-based fraud analytics
- image verification
- OCR validation
- model artifact persistence
- alerting and export workflows
- authentication and role separation
