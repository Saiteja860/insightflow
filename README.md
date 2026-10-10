# InsightFlow

**Intelligent Customer Feedback & Decision Platform**

InsightFlow collects customer feedback from multiple channels, analyzes sentiment,
urgency and themes, summarizes what customers care about, and turns those signals
into prioritized, trackable decisions.

## Features

| Capability | Status in this MVP |
|---|---|
| Feedback ingestion (web form + API, multi-source tags) | Done |
| Sentiment analysis (lexicon, negation & intensifier aware) | Done |
| Theme detection (pricing, performance, reliability, usability, support, delivery, features) | Done |
| Urgency scoring (1–5) | Done |
| Insights dashboard (KPIs, NPS-style score, theme breakdown) | Done |
| Decision engine (rule-based, priority + rationale) | Done |
| Decision tracking (open / in progress / done / dismissed) | Done |
| Sample data loader | Done |
| ML-based sentiment (transformers) / LLM summaries | Planned: swap in `app/analysis.py` |
| Auth, multi-tenant, connectors (Zendesk, Intercom, Slack) | Planned |

## Architecture

```
insightflow/
├── app/
│   ├── analysis.py   # sentiment, themes, urgency (swappable ML layer)
│   ├── insights.py   # aggregation + decision generation
│   ├── db.py         # SQLite persistence
│   ├── seed.py       # sample feedback
│   └── main.py       # FastAPI app: REST API + dashboard
├── static/index.html # dashboard (no build step)
├── tests/test_core.py
└── requirements.txt
```

## Quick start

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000, click **Load sample data**, then **Generate decisions**.

Run tests:

```bash
pytest -q
```

## REST API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/feedback` | Submit feedback `{text, source, customer_id?, channel?}`; returns analysis |
| GET | `/api/feedback?limit=&sentiment=` | List recent feedback |
| GET | `/api/insights` | Aggregated KPIs and theme statistics |
| POST | `/api/decisions/generate` | Create recommendations from current data |
| GET | `/api/decisions` | List decisions |
| PATCH | `/api/decisions/{id}` | Update status |
| POST | `/api/seed?reset=true` | Load sample data |
| GET | `/api/health` | Health check |

Interactive docs: `/docs`.

### Example

```bash
curl -X POST localhost:8000/api/feedback -H 'Content-Type: application/json' \
  -d '{"text":"Checkout keeps crashing and I was charged twice","source":"email"}'
```

## How the decision engine works

1. Each theme is aggregated: mention count, average sentiment, share of negative
   mentions and average urgency.
2. Themes with enough mentions and a negative signal become decisions.
3. Priority: `critical` if average urgency ≥ 4; `high` if ≥ 60% negative;
   `medium` if ≥ 40% negative; otherwise `low`.
4. Each decision carries a human-readable rationale for auditability.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `INSIGHTFLOW_DB` | `data/insightflow.db` | SQLite file path |
