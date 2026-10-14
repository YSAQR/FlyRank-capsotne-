# Architecture

## System diagram

```text
                    ┌──────────────┐
                    │   Client     │
                    └──────┬───────┘
                           │ HTTP
                           ▼
                 ┌─────────────────────┐
                 │ FastAPI (thin HTTP) │
                 │  health tenants     │
                 │  usage  generate    │
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

## Data flows

### Billable generate (`POST /generate`)

1. Validate body + `Idempotency-Key`.
2. Resolve tenant from `X-Tenant-Id` after checking `X-Dev-Token`.
3. Open a transaction; lock the tenant's subscription row (`FOR UPDATE`).
4. Insert or fetch the idempotency record (unique constraint is the race winner).
5. On hit: if request hash matches, return stored response; else `409`.
6. If subscription is not billable (`canceled`, missing, `past_due`, `unpaid`) → `402`.
7. Sum usage in the current period; reject with `429` if API or token quota would be exceeded.
8. Insert `api_call` (qty 1) and `ai_tokens` (qty = sum of token fields) usage events with derived keys `{client_key}:api_call` and `{client_key}:ai_tokens`.
9. Persist pricing snapshot (`pricing_version`, `cost_nano_usd`) on the token event.
10. Store response JSON on the idempotency record and commit.

Row locking serializes quota decisions per tenant. Uniqueness prevents double inserts under retries.

### Usage summary (`GET /usage`)

Aggregate `usage_events` for the tenant's current period (subscription window or UTC month). Plans come from the locked-in subscription/plan rows. Cost is summed `cost_nano_usd`, never inferred from quantity × a live rate (historical snapshot stays accurate).

### Stripe Checkout and webhooks

Checkout creates or reuses `stripe_customer_id`, then a Checkout Session for the configured test Price ID. Success redirects are **not** treated as payment.

Webhooks: raw body + `Stripe-Signature` → `stripe.Webhook.construct_event`. Invalid signature → `400`. Event id inserted uniquely; unique violation → ignore. Handlers update subscription plan/status/period in the same transaction as the event insert.

### Monthly reconciliation job

Reads events, upserts `monthly_usage_summaries` on `(tenant_id, period_start)`. Reruns overwrite with the same aggregates (idempotent). Bounded exponential backoff; failures emit a structured `ALERT` log line (local demo notification).

## Isolation and security

- Every tenant-scoped query filters by the authenticated tenant id from the header after token check — never from an untrusted body field alone.
- Secrets stay in environment variables; logs omit tokens, Stripe secrets, and raw webhook payloads beyond event id/type.
- Stripe live mode is rejected at settings load if a non-test key is provided.
