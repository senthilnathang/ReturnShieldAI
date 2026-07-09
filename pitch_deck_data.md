# ReturnShieldAI — Pitch Deck Data

## 1. Problem: The $50B Return Fraud Blind Spot

E-commerce returns fraud is the fastest-growing financial crime category that most fraud platforms miss entirely.

- **$50B+** in annual return fraud losses globally (2025), growing 18% YoY
- **13.7% return rate** industry average — every 1 in 7 orders gets returned
- **67% of merchants** report increased return fraud YoY (NRF 2025)
- **Existing solutions** (Signifyd, Forter, Sift) focus on checkout/payment fraud — returns happen *after* checkout, so they are invisible to these systems
- **Returns are uniquely exploitable**: empty-box scams, weight fraud, wardrobing, price arbitrage, FNOS (item not received), freight forwarding abuse

**Why returns are different:**
| Dimension | Payment Fraud | Return Fraud |
|---|---|---|
| Detection point | Checkout (pre-transaction) | Post-fulfillment (days later) |
| Data signals | ~50 features | 200+ features across order, shipment, customer, text, graph |
| Attack surface | Card details | Physical goods, labels, weight, chat transcripts, photos |
| Existing coverage | Excellent (stripe, sift, forter) | Near zero |

## 2. Solution: ReturnShieldAI

The first purpose-built, multi-engine AI platform purpose-built for e-commerce return fraud detection.

**Core value proposition:**
> Deploy in 5 minutes via API. Get a risk score, decision, and full explainability on every return request — before you release the refund.

**Key capabilities:**
- 20 modular engines covering structured ML, NLP, graph analytics, image verification, SHAP explainability, LLM investigation
- Real-time scoring (sub-500ms per request)
- Out-of-box fraud rules + trainable ML models
- Fraud ring detection via graph analysis (NetworkX + PageRank + Louvain)
- Full explainability — every score has a human-readable decision trace and why-flagged summary

## 3. Market Opportunity

| | Value |
|---|---|
| **TAM** (Global e-commerce fraud prevention) | $48.2B by 2030 (CAGR 18.3%) |
| **SAM** (Return fraud + post-purchase protection) | $8.7B by 2028 |
| **SOM** (Mid-market merchants with 10K-500K orders/mo) | $1.2B addressable |

**Target verticals:**
- Fashion & apparel (25-40% return rates)
- Electronics (15-25% return rates, high-value targets)
- Luxury goods (high ASP, organized fraud rings)
- Grocery delivery (identity fraud via multiple accounts)
- Marketplaces (multi-merchant fraud at scale)

## 4. Product Architecture

```
Return Request (REST API)
    │
    ├── Rule Engine (hard controls, 30% weight)
    ├── Structured ML (RandomForest/LightGBM/XGBoost families, 30%)
    ├── NLP Detection (sentence-transformers + TF-IDF, 25%)
    ├── Anomaly Detection (IsolationForest + statistical, 15%)
    ├── Fraud Ring Graph (NetworkX PageRank + Louvain communities)
    ├── Image Verification (OCR + photo similarity)
    │
    ├── Fusion Engine (weighted ensemble + meta learner)
    ├── SHAP Explainability
    ├── LLM Investigation Assistant
    │
    └── Output: Risk score (0-100), decision, reason codes, 
                explainability panel, decision trace
```

**Decision thresholds:**
| Score | Decision | Action |
|---|---|---|
| 0-39 | AUTO_APPROVE | Release refund immediately |
| 40-69 | MANUAL_REVIEW | Queue for analyst review |
| 70-100 | HOLD_REFUND_HIGH_RISK | Hold refund, senior analyst |

## 5. Technology Stack

20 modular engines, 24 REST API endpoints, full frontend dashboard:

- **NLP Engine**: sentence-transformers + TF-IDF hybrid (handles cold-start)
- **Vector DB**: FAISS with Qdrant-compatible interface (50+ embedding dimensions)
- **Fraud Ring**: NetworkX + PageRank + Louvain community detection
- **Explainability**: SHAP values + decision traces
- **Fusion**: Weighted ensemble (30/30/25/15 split) + meta learner
- **Alert Engine**: Slack, Email, Webhook integration
- **Monitoring**: Evidently AI drift detection + performance tracking
- **Model Registry**: joblib versioning with rollback support
- **LLM Investigation**: Explains every decision in plain language

**Data ingestion:**
- REST API for real-time scoring
- Kaggle import (2-phase: preview → auto-mapping → bulk import)
- Multi-file relational join for complex datasets (Olist-style)

## 6. Traction (Prototype Phase)

- ✅ 20 modular engines built and tested
- ✅ 24 REST API endpoints
- ✅ Full frontend dashboard (React + TypeScript + Tailwind)
- ✅ 3 Kaggle datasets imported (>2M rows across e-commerce domains)
- ✅ 50+ auto-mapping patterns for e-commerce data
- ✅ 18 seeded customers, 105 orders, 50 embeddings, full graph
- ✅ Case management with pagination, search, filter
- ✅ Feedback loop (analyst decisions retrain models)
- ✅ GitHub repo with production-quality code

**Deployment stats:**
- Return scoring: ~150ms per request (inference)
- Startup: ~12 seconds (model loading)
- Database: SQLite (dev) / PostgreSQL-ready (production)
- ML Models: 5 families trained on startup (structured, NLP, anomaly, fusion, graph)

## 7. Business Model

| Tier | Monthly Price | Volume | Features |
|---|---|---|---|
| **Starter** | $999/mo | Up to 10K returns/mo | Core scoring, dashboard, email alerts |
| **Growth** | $4,999/mo | Up to 100K returns/mo | All engines, Slack/Webhook, fraud ring, custom rules |
| **Enterprise** | Custom | Unlimited | On-prem, dedicated ML, LLM investigation, custom integrations |

**Revenue drivers:**
- Per-return pricing: $0.05-0.10 per scoring event (enterprise)
- Implementation fee: $5K-25K one-time
- Marketplace model: percentage of fraud prevented

## 8. Competitive Landscape

| | ReturnShieldAI | Signifyd | Forter | Sift | NoFraud |
|---|---|---|---|---|---|
| Return fraud focus | ★★★★★ Primary | ★☆☆☆☆ Afterthought | ★☆☆☆☆ Afterthought | ★★☆☆☆ Partial | ★★☆☆☆ Partial |
| Post-purchase | ★★★★★ Yes | ★☆☆☆☆ No | ★☆☆☆☆ No | ★★☆☆☆ Limited | ★★☆☆☆ Limited |
| Fraud ring detection | ★★★★★ NetworkX + PageRank | ★★☆☆☆ Basic | ★★☆☆☆ Basic | ★★★☆☆☆ | ★☆☆☆☆ |
| NLP on return text | ★★★★★ sentence-transformers | ★☆☆☆☆ | ★☆☆☆☆ | ★★☆☆☆ | ★☆☆☆☆ |
| Explainability | ★★★★★ Full SHAP + LLM | ★★★☆☆☆ | ★★★☆☆☆ | ★★★☆☆☆ | ★★☆☆☆ |
| Open source core | ★★★★★ Yes | ☆☆☆☆☆ No | ☆☆☆☆☆ No | ☆☆☆☆☆ No | ☆☆☆☆☆ No |
| Deployment | Self-hosted or cloud | Cloud-only | Cloud-only | Cloud-only | Cloud-only |
| Time to value | Minutes | Weeks | Weeks | Days | Days |

## 9. Competitive Moat

1. **Purpose-built for returns** — not a checkout fraud tool retrofitted
2. **Multi-engine architecture** — no single point of failure, each engine cross-validates others
3. **Fraud ring detection** — graph-based discovery of organized return fraud rings (unique in market)
4. **Full explainability** — regulators and analysts demand to know *why*
5. **Self-hosted option** — for data-sensitive enterprises that won't share data with cloud-only vendors
6. **NLP on return narratives** — return reasons and chat transcripts contain rich fraud signals invisible to traditional models

## 10. Team

- **CEO / ML Lead** — ML engineering background, built production fraud systems
- **Full-stack** — React + Python, end-to-end product ownership
- **Engineering-driven culture** — 20 modules built in weeks, not months

## 11. Ask

**Seed Round: $750K**

| Use of Funds | % | Amount |
|---|---|---|
| Engineering (3 FTE, 12 months) | 55% | $412K |
| Customer pilots (3-5 merchants) | 15% | $112K |
| Cloud infrastructure | 12% | $90K |
| Compliance & legal | 10% | $75K |
| Marketing & GTM | 8% | $60K |

**Milestones (12 months):**
- 5 paying customers (enterprise pilots)
- 1M+ monthly returns scored
- 3 pre-built integrations (Shopify, Magento, BigCommerce)
- SOC 2 Type I certification
- Revenue run rate: $300K ARR

**Target investors:**
- Enterprise SaaS / fintech infrastructure VCs
- E-commerce / logistics focused funds
- AI/ML specialist investors
- Strategic angels from Stripe, Shopify, Forter

---

*Generated: `pitch_deck.html` (interactive slides) and `pitch_deck_returnshield.pdf` (print-ready, A4)*
