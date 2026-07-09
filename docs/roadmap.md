# ReturnShield AI - Roadmap

## Phase 1: Hackathon MVP - Complete

Single-process FastAPI + SQLite system with the full fraud decisioning pipeline.

- [x] Return intake + scoring API
- [x] 5 ML model families (structured, NLP, anomaly, graph, fusion)
- [x] Rule engine with JSON-backed conditions
- [x] Case management with pagination, search, filter
- [x] Analyst decision workflow + feedback capture
- [x] Dashboard metrics
- [x] Synthetic seed data (100+ records, 9 fraud patterns)
- [x] React frontend with 7 UI pages
- [x] 20 modular engine stubs
- [x] Kaggle import with auto-mapping
- [x] FAISS embedding + Qdrant-compatible vector engine
- [x] VC pitch deck (data, HTML slides, PDF)

## Phase 2: Production Foundation - Complete

PostgreSQL 15 + Redis 7 + FastAPI + SQLAlchemy 2.0 async + Docker Compose.

- [x] 17 normalized database tables with UUID PKs, FK constraints, BRIN/GIN/composite indexes
- [x] Alembic migration (001_initial_schema)
- [x] Generic BaseRepository<T> + specialized repos (Customer, Order, Return, Fraud, Dashboard)
- [x] Async services: Import, Cache, Dashboard, Realtime, Scoring Stub
- [x] 21 REST API endpoints under /api/v1 (health, imports, returns, fraud-cases, dashboard, customers, orders)
- [x] Redis Streams for async scoring queue (consumer group: scoring-workers)
- [x] Redis Pub/Sub for real-time dashboard events
- [x] Redis TTL caching for dashboard aggregations
- [x] Background workers (realtime_worker, import_worker)
- [x] Scoring stub with 8 rule conditions
- [x] Docker Compose (PostgreSQL, Redis, Backend)
- [x] Kaggle import pipeline with auto-mapping (28+ column aliases)
- [x] Seed demo data script (merchant, rules, customers, returns)
- [x] pytest test suite (models, scoring, dashboard, import, health)
- [x] Developer documentation

## Phase 3: Supervised ML Engine - In Progress

The new production ML layer is implemented and now becomes the next iteration focus.

- [x] PostgreSQL-backed feature loader and leakage-safe feature store
- [x] Logistic Regression baseline with class weighting
- [x] Random Forest tabular model
- [x] XGBoost high-performance model
- [x] Neural Network model with PyTorch fallback path
- [x] Model registry with artifact persistence and promotion
- [x] Training comparison stored in PostgreSQL (`model_training_runs`)
- [x] Prediction API under `/api/v1/ml/predict`
- [x] Batch prediction and training APIs
- [x] Best-model promotion into `backend/models/best_model/`
- [x] Redis prediction cache and training progress stream
- [x] Score fallback when no artifact exists
- [ ] Add SHAP-based explanations
- [ ] Add hyperparameter search / cross-validation sweeps
- [ ] Add scheduled retraining cadence
- [ ] Add drift monitoring and threshold recalibration

## Phase 4: Enterprise Features

- [ ] Multi-tenancy with full merchant isolation
- [ ] Role-based access control (admin, analyst, viewer)
- [ ] Audit logging for all data access
- [ ] Webhook notifications (Slack, email, custom)
- [ ] SHAP explainability integration
- [ ] LLM investigation assistant
- [ ] Image verification (OCR + photo similarity)
- [ ] Rate limiting per merchant API key
- [ ] Prometheus metrics + Grafana dashboards
- [ ] SOC 2 compliance readiness

## Phase 5: Scale

- [ ] Horizontal worker scaling (multiple replicas of realtime_worker)
- [ ] Read replicas for PostgreSQL dashboard queries
- [ ] Redis Cluster for high-throughput queues
- [ ] Batch scoring API for offline/historical data
- [ ] Export workflows (CSV, PDF reports)
- [ ] API versioning strategy (v1, v2)
- [ ] SDK for Shopify, Magento, BigCommerce
- [ ] Managed cloud offering
