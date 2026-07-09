# ReturnShield AI
## Rule-led supervised fraud scoring for return decisions

**Bifold copy source**

### Front Cover
ReturnShield AI scores every return request, explains the decision, and helps merchants stop bad refunds before money leaves the system.

Built for the fraud surface checkout tools miss: empty-box claims, wardrobing, item swaps, fraud rings, and suspicious return narratives.

- Risk score from `0` to `100`
- `AUTO_APPROVE`, `MANUAL_REVIEW`, `HOLD_REFUND`
- Human-readable explanations
- Real-time and batch scoring

### Back Cover
ReturnShield AI turns returns into an operational control point: score, explain, review, and learn.

- Fewer wrongful refunds
- Faster review for legitimate returns
- Better analyst consistency
- Stronger escalation evidence

<div style="page-break-after: always;"></div>

# Inside Left
## Product Features

ReturnShield AI works as an operational fraud console, not just a scoring endpoint.

- Return scoring before the refund is released
- Explainability in plain language
- Case review for medium and high risk returns
- Feedback loop for retraining and follow-up
- Fraud ring visibility across connected accounts
- Reason codes that support analyst action

### Decision Path
1. Return request arrives.
2. Payload is normalized.
3. Rules and supervised ML score the case.
4. NLP, graph, and anomaly signals support explanation.
5. The return is approved, reviewed, or held.
6. Analyst feedback is stored for improvement.

<div style="page-break-after: always;"></div>

# Inside Right
## Algorithm and Accuracy

ReturnShield AI uses a rule-led supervised model for the live score. NLP, graph, and anomaly signals remain available for explanation and manual review.

### Scoring Formula
```text
final_score =
  (rule_score * 0.35) +
  (ml_score * 0.65)
```

### Fallback
- If the promoted model artifact is unavailable, the scorer uses a heuristic fallback.
- The API still returns a decision so operations keep flowing.

### Decision Bands
- `0-39` -> `AUTO_APPROVE`
- `40-69` -> `MANUAL_REVIEW`
- `70-100` -> `HOLD_REFUND`

### Accuracy Story
- PR-AUC is the primary model-selection metric
- Recall and precision are tracked for fraud imbalance
- F1 and false positive rate are used to break ties
- Training runs and metrics are stored in PostgreSQL

The repo supports four supervised model families: Logistic Regression, Random Forest, XGBoost, and a PyTorch neural network. It documents the evaluation pipeline, but it does not invent benchmark percentages.
