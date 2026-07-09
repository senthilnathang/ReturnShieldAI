# ReturnShield AI## Return fraud decisioning that catches what checkout fraud tools miss

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

### Typical Workflow
1. Return request arrives.
2. Payload is normalized.
3. Rules and models score the case.
4. The return is approved, reviewed, or held.
5. Analyst feedback is stored for improvement.

<div style="page-break-after: always;"></div>

# Inside Right
## Algorithm and Accuracy

ReturnShield AI combines rules, structured ML, NLP, and anomaly detection instead of trusting any single field.

### Scoring Formula
```text
final_score =
  (rule_score * 0.30) +
  (structured_ml_score * 0.30) +
  (nlp_score * 0.25) +
  (anomaly_score * 0.15)
```

### Decision Bands
- `0-39` -> `AUTO_APPROVE`
- `40-69` -> `MANUAL_REVIEW`
- `70-100` -> `HOLD_REFUND`

### Accuracy Story
- Precision on obvious fraud
- Recall on subtle fraud
- Consistency across repeated cases
- Reviewability for analysts and auditors

The repo tracks precision, recall, and F1 in training runs, but it does not publish audited benchmark percentages. That keeps the pitch credible and print-safe.
