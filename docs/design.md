# Design — FlyRank usage metering & billing engine

## Problem

SaaS products need a trustworthy record of who used what, whether that usage is still inside a plan, and what it cost. Naïve counters fail under retries and concurrency: the same request is counted twice, or two requests together spend more quota than exists. This service is a small, correct billing core for two plans (Free and Pro) with idempotent metering, atomic quotas, integer token pricing, and Stripe test-mode subscription sync.

## Data model

- **Tenant** — customer organization (`id`, `name`, `status`, `created_at`).
- **Plan** — `free` / `pro` with monthly API-call and AI-token quotas.
- **Subscription** — one per tenant: plan, Stripe ids, status, current period window.
- **UsageEvent** — one billable increment (`api_call` or `ai_tokens`) with quantity, cost snapshot, request hash, and an idempotency key unique per tenant.
- **IdempotencyRecord** — maps `(tenant_id, key)` to the original HTTP status + body and a payload fingerprint.
- **StripeEvent** — processed Stripe event ids (unique) so webhooks are exactly-once at the application layer.
- **MonthlyUsageSummary** — idempotent aggregation written by the reconciliation job; HTTP `/usage` still aggregates from `usage_events` as source of truth.

## API surface

| Method | Path | Auth | Role |
| --- | --- | --- | --- |
| GET | `/health` | none | liveness + DB ping |
| POST | `/tenants` | `X-Dev-Token` | create tenant + Free subscription |
| GET | `/usage` | tenant | monthly usage summary |
| POST | `/generate` | tenant + `Idempotency-Key` | dummy billable generation |
| POST | `/billing/checkout` | tenant | Stripe Checkout Session (Pro) |
| POST | `/webhooks/stripe` | Stripe signature | subscription sync |

Development identity: `X-Tenant-Id` + `X-Dev-Token`. This is **not** production authentication.

## Layer sketch

`routes → services → repositories/SQLAlchemy → PostgreSQL`

Routes validate and map errors to HTTP. Services own idempotency, quotas, pricing, and Stripe. Repositories hide queries. Critical billing work runs in a single DB transaction with `SELECT … FOR UPDATE` on the tenant subscription row.

## Policies (explicit)

- **Idempotency:** unique `(tenant_id, idempotency_key)` on both records and usage events. Replay with the same payload returns the stored result. Same key, different payload → `409`.
- **Quota:** allowed iff `current + requested <= quota`. Overspend → `429`. Missing/inactive/past-due subscription → `402`.
- **Period:** Stripe period when present; otherwise UTC calendar month.
- **Money:** integer **nano-USD** (`1 USD = 1_000_000_000`). No floats.
- **Tokens on `/generate`:** `input_tokens` means *fresh* input. Cached, output, and reasoning are separate. Reasoning is billed at the output rate once. Quota counts the sum of all four quantities plus one API call.

## One explicit non-goal

No invoices, proration, overage billing, production IdP, or live Stripe charges. Stretch billing features are out of scope until the core engine is correct.
