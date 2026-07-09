# Sample Data

## Hackathon MVP

The backend seeds the database on startup via `backend/app/ml/sample_data_generator.py`.

Includes 100+ return records with patterns:
- legitimate returns
- suspicious returns
- confirmed fraud examples
- high-value returns
- weight mismatch returns
- repeated return-reason text
- serial returner customers
- shared address fraud ring
- chargeback fraud cases

## Production Foundation

Seeded via `python app/scripts/seed_demo_data.py` which creates:
- 1 demo merchant (ReturnShield Demo)
- 7 default rules (high return frequency, weight mismatch, quick return, etc.)
- 2 customers with shared address identity (fraud ring signal)
- 4 orders + returns with varying risk profiles
- Fraud scores and cases for each return

## Kaggle Import

Large datasets can be imported via:
```bash
python app/scripts/import_kaggle_dataset.py --file data/kaggle_returns.csv
```
Auto-maps 28+ column aliases, creates customers/orders/shipments/returns/identities,
tracks progress in `import_jobs` table.
