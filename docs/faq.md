# ReturnShield AI FAQ

## What is ReturnShield AI?

A hackathon MVP for shipment return fraud detection.

## Is this a clone of Marble?

No. It is inspired by the useful product ideas only: decisioning, rules, scoring, explanation, and analyst review. The implementation is custom and intentionally smaller.

## How do I run it locally?

Use local dev mode:

```bash
./run.sh install all
./run.sh run dev
```

## How do I reset the demo data?

```bash
./run.sh load demo
```

If Docker is available, that command resets and reloads the Compose demo stack. Otherwise it resets the local SQLite demo database.

## What ports are used?

- backend: `8000`
- frontend: `5173`

## What database does local dev use?

SQLite by default.

## What database does Compose mode use?

PostgreSQL.

## What is the scoring logic?

A weighted fusion of:

- rules
- structured ML
- NLP ML
- anomaly detection

## How are cases explained?

Every case includes:

- final risk score
- decision bucket
- recommended action
- score breakdown
- reason codes
- short explanation

## Can analysts give feedback?

Yes. Analyst actions are stored in the database and can be used later for retraining.
