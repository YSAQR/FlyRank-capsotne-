# FlyRank Usage Metering & Billing Engine

A backend billing core that answers the three questions every SaaS must solve: **how much has this customer used?** **What does it cost?** **Have they hit their plan limits?**

Built with FastAPI, PostgreSQL, SQLAlchemy 2, Alembic, and Stripe TEST mode.

---

## Architecture

```text
                    ┌──────────────┐
                    │    Client    │
                    └──────┬───────┘
                           │ HTTP
                           ▼
                 ┌─────────────────────┐
                 │ FastAPI (thin HTTP) │
                 │  health  tenants    │
                 │  usage   generate   │
                 │  billing  webhooks  │
                 └──────────┬──────────┘
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
   metering/quota     pricing/usage      stripe/subscription
     services            services            services
          │                 │                 │
          └────────┬────────┴────────┬────────┘
                   ▼                 ▼
            SQLAlchemy 2        Stripe TEST API
                   │
                   ▼
              PostgreSQL
         constraints + row locks
                   ▲
                   │
            monthly_usage_job
            (CLI, retries, alerts)
```

### Layer separation

- **Routes** (`app/api/routes/`) — validate HTTP, map errors, delegate to services.
- **Services** (`app/services/`) — idempotency, quota checks, pricing, Stripe orchestration.
- **Repositories** (`app/repositories/`) — raw SQL queries, savepoints, session management.
- **Models** (`app/db/models/`) — SQLAlchemy 2.0 mapped ORM tables.

---

## Plans & quotas

| Plan | API calls / month | AI tokens / month |
| ---- | -----------------:| -----------------:|
| Free | 1,000 | 100,000 |
| **Pro** | **100,000** | **10,000,000** |

Pricing rates (demo, configurable via environment):

| Token type | Rate (nano-USD / token) | Equivalent (USD / 1M tokens) |
| ---------- | -----------------------:| ----------------------------:|
| Fresh input | 3,000 | $3.00 |
| Cached input | 300 | $0.30 |
| Output | 15,000 | $15.00 |
| Reasoning | 15,000 (output rate) | $15.00 |

Money is stored as **integer nano-USD** (1 USD = 1,000,000,000 nano-USD). No floats, ever.

---

## API endpoints

| Method | Path | Auth | Purpose |
| ------ | ---- | ---- | ------- |
| GET | `/health` | none | Liveness + DB ping |
| POST | `/tenants` | `X-Dev-Token` | Create tenant + Free subscription |
| GET | `/usage` | tenant | Monthly usage summary (used, allowed, cost) |
| POST | `/generate` | tenant + `Idempotency-Key` | Dummy billable AI generation |
| POST | `/billing/checkout` | tenant | Create Stripe Checkout Session (upgrade to Pro) |
| POST | `/webhooks/stripe` | Stripe signature | Subscription sync from Stripe events |

**Development identity:** every tenant-scoped request requires two headers:
- `X-Dev-Token` — matches the `TENANT_DEV_TOKEN` env var.
- `X-Tenant-Id` — a valid tenant UUID.

This is development-only authentication, not production.

---

## Quick start

### Prerequisites

- Docker & Docker Compose
- (Optional) Stripe CLI for live webhook testing

### Run

```bash
# 1. Clone the repo
git clone https://github.com/<your-username>/flyrank-capstone-metering-billing.git
cd flyrank-capstone-metering-billing

# 2. Copy and configure environment
cp .env.example .env
# Edit .env if you have Stripe test keys (optional — mocked in tests)

# 3. Start everything (Postgres + API)
docker compose up --build

# The API auto-runs: alembic upgrade head → seed → uvicorn on :8000
```

### Seed demo data

Demo data is seeded automatically on `docker compose up`. To re-seed manually:

```bash
docker compose exec api python -m app.db.seed
```

This creates:
- **Free** and **Pro** plans with the quotas above.
- A demo tenant (`11111111-1111-1111-1111-111111111111`) on the Free plan.

### Run tests

```bash
docker compose exec api pytest
```

### Try it

```bash
# Health check
curl http://localhost:8000/health

# Create a tenant
curl -X POST http://localhost:8000/tenants \
  -H "X-Dev-Token: change-me-dev-token" \
  -H "Content-Type: application/json" \
  -d '{"name": "Acme Corp"}'

# Generate (billable endpoint)
curl -X POST http://localhost:8000/generate \
  -H "X-Dev-Token: change-me-dev-token" \
  -H "X-Tenant-Id: 11111111-1111-1111-1111-111111111111" \
  -H "Idempotency-Key: my-first-request" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Explain reverse proxies", "input_tokens": 120, "cached_input_tokens": 20, "output_tokens": 80, "reasoning_tokens": 15}'

# Check usage
curl http://localhost:8000/usage \
  -H "X-Dev-Token: change-me-dev-token" \
  -H "X-Tenant-Id: 11111111-1111-1111-1111-111111111111"
```

---

## Key design decisions

1. **Idempotency** — Two layers: `idempotency_records` stores full HTTP responses keyed by `(tenant_id, key)` with a SHA-256 payload fingerprint. `usage_events` has a unique constraint on `(tenant_id, idempotency_key)`. Same payload replays the cached response; different payload returns `409 Conflict`.

2. **Atomic quota enforcement** — `SELECT … FOR UPDATE` on the subscription row serializes concurrent requests per tenant. Usage is summed in the current billing period and compared against plan limits before any event is recorded. No overspend possible.

3. **Billing period** — Uses the Stripe subscription period (`current_period_start` / `current_period_end`) when present; falls back to UTC calendar month.

4. **Stripe webhook safety** — Signature verified via `stripe.Webhook.construct_event`. Event IDs stored in `stripe_events` with a unique primary key — duplicates are silently ignored. Forged webhooks return `400`.

5. **Money** — Integer nano-USD throughout. Pricing snapshots are written on each usage event so historical costs remain accurate even if rates change later.

---

## Project structure

```
app/
├── api/
│   ├── dependencies.py      # Auth + tenant resolution
│   └── routes/               # Thin HTTP handlers
├── core/
│   ├── config.py             # Pydantic settings (env vars)
│   ├── exceptions.py         # Domain error hierarchy
│   └── logging.py            # JSON logging + secret filter
├── db/
│   ├── models/               # SQLAlchemy 2 ORM models
│   ├── seed.py               # Idempotent seed script
│   └── session.py            # Session factory
├── jobs/
│   ├── monthly_usage_job.py  # Background reconciliation
│   └── retry_utils.py        # Exponential backoff
├── repositories/             # Data access layer
├── schemas/                  # Pydantic request/response models
├── services/                 # Domain logic (metering, quota, pricing, Stripe)
└── utils/                    # Hashing, money formatting, period math
alembic/
├── versions/
│   └── 0001_initial_schema.py
tests/
├── api/                      # HTTP endpoint tests
├── billing/                  # Quota boundary tests
├── integration/              # Concurrency, transactions, migrations, job
├── unit/                     # Pricing math, retry logic
└── webhooks/                 # Stripe signature + event dedup tests
```

---

## Limitations

- **Development authentication only.** Tenant identity relies on `X-Tenant-Id` + `X-Dev-Token` headers. There is no production IdP, JWT, or OAuth integration.
- **No real AI model calls.** `POST /generate` is a dummy endpoint that meters token counts provided in the request body. No external AI API is called.
- **Stripe TEST mode only.** Live Stripe keys are rejected at startup. No real money is ever moved.
- **No invoicing, proration, or overage billing.** The system enforces hard quota limits; there is no mid-cycle upgrade proration or overage charge calculation.
- **Single-instance only.** The row-locking strategy works within a single PostgreSQL instance. Horizontal scaling would require distributed locking.
- **GitHub repo creation blocked.** The `gh` CLI was not authenticated on the build machine; the repo needs to be created manually or after `gh auth login`.
