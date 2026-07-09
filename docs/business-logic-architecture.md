# ReturnShield AI Business Logic Architecture

This diagram shows the current production decision path from return intake to model feedback.

```mermaid
flowchart TD
  A[Return request created] --> B[Persist customer, order, shipment, return]
  B --> C[Build features from PostgreSQL]
  C --> D[Evaluate rule engine]
  C --> E[Load promoted supervised model]
  E --> F{Model artifact available?}
  F -- Yes --> G[Predict fraud probability]
  F -- No --> H[Heuristic fallback score]
  D --> I[Rule score]
  G --> J[ML score]
  H --> J
  I --> K[Combine live score]
  J --> K
  K --> L[Final score 0-100]
  L --> M{Decision band}
  M -- 0-39 --> N[AUTO_APPROVE]
  M -- 40-69 --> O[MANUAL_REVIEW]
  M -- 70-100 --> P[HOLD_REFUND]
  N --> Q[Store fraud score]
  O --> Q
  P --> Q
  Q --> R[Create / update fraud case]
  R --> S[Publish to Redis stream and cache]
  S --> T[Analyst review]
  T --> U[Analyst feedback stored]
  U --> V[Retraining queue]
  V --> W[Model comparison and promotion]
```

## Current Decision Logic

- The live production score is rule-led and supervised-ML weighted.
- NLP, graph, and anomaly signals remain supporting evidence for explanation.
- The scorer falls back to a heuristic path when no promoted artifact exists.
- Every score is retained for audit, review, and retraining.

## Model Lifecycle

1. Pull training rows from PostgreSQL.
2. Preprocess structured and categorical features.
3. Train Logistic Regression, Random Forest, XGBoost, and Neural Network models.
4. Compare models primarily by PR-AUC, then F1, then false positive rate.
5. Promote the best artifact into `backend/models/best_model/`.
6. Cache metadata in Redis for fast lookups.
