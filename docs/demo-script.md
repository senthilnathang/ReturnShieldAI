# ReturnShield AI Demo Script

Use this script to walk through the product in a live demo.

## 1. Start the app

### Hackathon MVP
```bash
./run.sh run dev
```
Reset demo data: `./run.sh load demo`

### Production Foundation
```bash
docker compose up -d
python app/scripts/seed_demo_data.py
```
Reset demo data: `python app/scripts/seed_demo_data.py`

## 2. Open the dashboard

- Frontend: `http://127.0.0.1:5173`
- API: `http://127.0.0.1:8000/docs`

## 3. Show the overview

Narration:
- This dashboard shows the current return-fraud queue.
- The score combines rules and supervised ML, with NLP, anomaly, and graph signals reserved for the broader fusion engine.
- High-risk returns are surfaced for analyst review.

Points to call out:
- total returns today
- high-risk cases
- manual review cases
- estimated fraud prevented
- average risk score
- risk distribution chart (0-19, 20-39, 40-59, 60-79, 80-100 score bands)
- best model type and version from the ML registry

## 4. Open the case queue

Narration:
- The queue is sorted by risk score.
- Analysts can search by customer, product, or return reason.
- Risk level and decision are exposed directly in the table.

Suggested cases to open:
- serial returner (high return frequency)
- weight mismatch (expected vs returned weight)
- reused fraud script (text and reason patterns)
- shared address/device fraud ring

## 5. Open a high-risk case

Narration:
- This case shows the score breakdown.
- The explanation is generated from the strongest triggers.
- Reason codes explain why the return was flagged.

Points to call out:
- customer profile (age, lifetime orders/returns, risk score)
- order details (product, SKU, value, delivery date)
- return details (reason, returned weight, condition)
- score breakdown (rule and ML bars)
- triggered rules
- suspicious phrases in the return reason
- timeline (return created -> scored -> analyst action)

## 6. Apply an analyst decision

Narration:
- The analyst can approve, reject, hold, or escalate the case.
- Feedback is stored so the model can learn from analyst decisions later.

Recommended action for the demo:
- Mark Confirmed Fraud
- Add a short note such as `Empty-box pattern plus shared device and repeat return behavior.`

## 7. Show the rules page

Narration:
- Rules are configurable without redeploying the app.
- A rule can be enabled or disabled quickly.
- Rule scores are part of the final fusion score.

Show one or two examples:
- high return frequency
- weight mismatch
- fast return after delivery

## 8. Show the ML engine page or API

Narration:
- The ML layer trains Logistic Regression, Random Forest, XGBoost, and Neural Network models from PostgreSQL.
- The best model is selected by PR-AUC, then F1, then false positive rate.
- Artifacts are versioned and promoted into `backend/models/best_model/`.

## 9. Show production-specific features (optional)

If running the production stack:
- **Redis Architecture**: dashboard caching, scoring queues, live pub/sub
- **API v1**: health checks, import jobs, paginated returns, fraud cases, ML prediction and training APIs
- **Workers**: `realtime_worker` consumes scoring stream, `import_worker` ingests CSV, `ml_training_worker` retrains models

## 10. Close with the value proposition

Suggested closing:
- ReturnShield AI gives analysts a clear fraud score, readable explanations, and a workflow to capture feedback.
- The demo proves the full journey from return request to analyst decision.
- The supervised ML layer makes the platform more adaptive without removing the rules that analysts trust.
- Purpose-built for returns - not a checkout fraud tool retrofitted.

## Optional Reset

```bash
./run.sh load demo          # Hackathon
python app/scripts/seed_demo_data.py  # Production
```
