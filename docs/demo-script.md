# ReturnShield AI Demo Script

Use this script to walk through the product in a live demo.

## 1. Start the app

Local dev mode:

```bash
./run.sh run dev
```

If you want to reset the seeded demo data first:

```bash
./run.sh load demo
```

## 2. Open the dashboard

- Frontend: `http://127.0.0.1:5173`
- Backend health: `http://127.0.0.1:8000/api/health`

## 3. Show the overview

Narration:

- This dashboard shows the current return-fraud queue.
- The score combines rules, structured ML, NLP, and anomaly detection.
- High-risk returns are surfaced for analyst review.

Points to call out:

- total returns today
- high-risk cases
- manual review cases
- estimated fraud prevented
- average risk score

## 4. Open the case queue

Narration:

- The queue is sorted by risk score.
- Analysts can search by customer, product, or return reason.
- Risk level and decision are exposed directly in the table.

Suggested case to open:

- serial returner
- weight mismatch
- reused fraud script
- shared address/device fraud ring

## 5. Open a high-risk case

Narration:

- This case shows the score breakdown.
- The explanation is generated from the strongest triggers.
- Reason codes explain why the return was flagged.

Points to call out:

- customer profile
- order details
- return details
- score breakdown
- triggered rules
- NLP phrases or script reuse
- timeline

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

## 8. Show the model page

Narration:

- This is a lightweight baseline model, not a heavy MLOps system.
- It still shows model versioning, precision, recall, and label volume.
- The system is designed to be extensible.

## 9. Close with the value proposition

Suggested closing:

- ReturnShield AI gives analysts a clear fraud score, readable explanations, and a workflow to capture feedback.
- The demo proves the full journey from return request to analyst decision.
- The MVP is intentionally small, but the architecture can grow into a larger fraud decision engine.

## Optional Reset

If you want to start over during the demo:

```bash
./run.sh load demo
```

If Docker Compose is available, this resets the containerized stack. Otherwise it reloads the local SQLite demo database.
