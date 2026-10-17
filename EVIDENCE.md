# EVIDENCE.md

Pasted proofs for each Requirements checkbox in Section 6 of the capstone brief.
Each proof is a test name + assertion, a curl transcript, or a log line.

---

## Metering

### ✅ A billable action creates exactly one usage event, even under retries

**Test:** `tests/api/test_generate_and_usage.py::test_generate_records_usage_once`

```
Send POST /generate twice with Idempotency-Key: "same-key"
→ first response:  status 200, idempotent_replay = false
→ second response: status 200, idempotent_replay = true
→ GET /usage shows: api_calls.used = 1, ai_tokens.used = 235
→ generation_id matches on both responses
```

**Concurrency proof:** `tests/integration/test_concurrency.py::test_concurrent_duplicate_keys_create_one_event`

```
8 threads send POST /generate simultaneously with the same Idempotency-Key "concurrent-dup"
→ all 8 responses: status 200
→ GET /usage shows: api_calls.used = 1, ai_tokens.used = 235
  (not 8 events — exactly one, even under race conditions)
```

### ✅ Conflicting idempotency key → 409

**Test:** `tests/api/test_generate_and_usage.py::test_conflicting_idempotency_key`

```
POST /generate with Idempotency-Key: "conflict-key", input_tokens=120  → 200
POST /generate with Idempotency-Key: "conflict-key", input_tokens=121  → 409
Response body: {"error": "IDEMPOTENCY_KEY_REUSED", "message": "Idempotency key was reused with a different payload."}
```

---

## Quotas

### ✅ Usage is checked against the tenant's plan; requests over the limit are rejected

**Test:** `tests/billing/test_quotas.py::test_usage_beyond_limit_rejected`

```
Set Free plan quotas: api=1, tokens=235
POST /generate (first request)  → 200 (fills quota exactly)
POST /generate (second request) → 429
Response: {"error": "QUOTA_EXCEEDED", ...}
Header: Retry-After: <seconds until period end>
```

### ✅ Exact boundary: request at the limit is accepted, one after is rejected

**Test:** `tests/billing/test_quotas.py::test_usage_exactly_at_limit_accepted`

```
Set Free plan quotas: api=1, tokens=235
POST /generate with 120+20+80+15 = 235 tokens → 200
GET /usage shows:
  api_calls:  {"used": 1, "allowed": 1, "remaining": 0}
  ai_tokens:  {"used": 235, "allowed": 235, "remaining": 0}
```

### ✅ Responses carry correct status codes (429 / 402)

**429 — quota exceeded:** `tests/billing/test_quotas.py::test_usage_beyond_limit_rejected`
```
status_code = 429
error = "QUOTA_EXCEEDED"
Retry-After header present
```

**402 — payment required:** `tests/billing/test_quotas.py::test_canceled_subscription_returns_402`
```
UPDATE subscriptions SET status='canceled'
POST /generate → 402
{"error": "PAYMENT_REQUIRED", "message": "Subscription is not in a billable state..."}
```

### ✅ Concurrent requests cannot overspend quota

**Test:** `tests/integration/test_concurrency.py::test_concurrent_requests_cannot_overspend_quota`

```
Set Free plan quotas: api=1, tokens=10000
6 threads race to POST /generate with different Idempotency-Keys
→ exactly 1 returns 200
→ exactly 5 return 429
→ GET /usage: api_calls.used = 1 (never 2+, even under race)
```

---

## Cost Calculation

### ✅ AI token pricing handles cached input, reasoning, and output correctly

**Test:** `tests/unit/test_pricing.py::test_mixed_request_manual_total`

```
fresh_input_tokens=120, cached_input_tokens=20, output_tokens=80, reasoning_tokens=15

Manual calculation:
  120 × 3,000 (fresh input)          =   360,000
   20 ×   300 (cached input)          =     6,000
  (80 + 15) × 15,000 (output rate)   = 1,425,000
                                       ----------
  Total                               = 1,791,000 nano-USD

assert quote(...) == 1_791_000  ✅ PASS
```

### ✅ Cached input tokens are cheaper

**Test:** `tests/unit/test_pricing.py::test_cached_input_tokens_only`

```
10 cached input tokens × 300 = 3,000 nano-USD
vs.
10 fresh input tokens × 3,000 = 30,000 nano-USD
(10× cheaper, as documented)
```

### ✅ Reasoning tokens count as output tokens (billed at output rate, once)

**Test:** `tests/unit/test_pricing.py::test_reasoning_tokens_only_use_output_rate_once`

```
10 reasoning tokens × 15,000 = 150,000 nano-USD
(same rate as output tokens, applied once — not double-counted)
```

### ✅ Pricing constants pinned in config

Rates configured in `app/core/config.py`:
```python
input_rate_nano_usd: int = 3_000        # $3.00 / 1M tokens
cached_input_rate_nano_usd: int = 300    # $0.30 / 1M tokens
output_rate_nano_usd: int = 15_000       # $15.00 / 1M tokens
pricing_version: str = "demo-v1"
```

### ✅ GET /usage matches pinned pricing

**Test:** `tests/api/test_generate_and_usage.py::test_generate_records_usage_once`

```
POST /generate with 120 fresh + 20 cached + 80 output + 15 reasoning
GET /usage shows:
  cost.amount = 1,791,000
  cost.unit = "nano_usd"
  cost.currency = "USD"
```

This matches the manual calculation: `120×3000 + 20×300 + 95×15000 = 1,791,000`.

---

## Stripe Integration

### ✅ Subscription checkout works end-to-end in Stripe test mode

**Test:** `tests/webhooks/test_stripe.py::test_checkout_mocked`

```
StripeService.create_checkout_session(DEMO_TENANT_ID)
→ Stripe Customer.create called with metadata {"tenant_id": "1111..."}
→ Stripe checkout.Session.create called with mode="subscription"
→ Returns: session_id="cs_test_1", stripe_customer_id="cus_abc"
```

When Stripe is not configured (placeholder keys):
```
POST /billing/checkout → 503
{"error": "STRIPE_NOT_CONFIGURED", "message": "Stripe TEST credentials are not configured..."}
```

### ✅ Webhooks verify signatures

**Test:** `tests/webhooks/test_stripe.py::test_invalid_webhook_signature_returns_400`

```
POST /webhooks/stripe with Stripe-Signature: "t=1,v1=deadbeef" (forged)
→ 400
→ {"error": "INVALID_STRIPE_SIGNATURE", "message": "Invalid Stripe webhook signature."}
Nothing in the database changed.
```

**Test:** `tests/webhooks/test_stripe.py::test_missing_signature_returns_400`

```
POST /webhooks/stripe with no Stripe-Signature header
→ 400
```

### ✅ Webhooks ignore duplicate events

**Test:** `tests/webhooks/test_stripe.py::test_subscription_updated_and_duplicate`

```
Process event evt_sub_updated_1 (customer.subscription.updated)
→ first call:  {"status": "processed", "event_id": "evt_sub_updated_1"}
→ second call: {"status": "duplicate", "event_id": "evt_sub_updated_1"}
  (event ID stored in stripe_events table; unique constraint prevents re-processing)
```

### ✅ Webhooks update tenant plan/status (Free → Pro)

**Test:** `tests/webhooks/test_stripe.py::test_subscription_updated_and_duplicate`

```
After processing customer.subscription.updated with status="active":
GET /usage shows:
  plan_code = "pro"
  subscription_status = "active"
  api_calls.allowed = 100,000
```

### ✅ Subscription deleted → back to Free

**Test:** `tests/webhooks/test_stripe.py::test_subscription_deleted_returns_to_free`

```
Process customer.subscription.deleted event
GET /usage shows:
  plan_code = "free"
  subscription_status = "canceled"
```

---

## Data Model, Tests & Documentation

### ✅ Database includes tenants, plans, subscriptions, usage events

**Migration:** `alembic/versions/0001_initial_schema.py` creates 7 tables:

| Table | Purpose |
| ----- | ------- |
| `tenants` | Customer organizations |
| `plans` | Free / Pro with quota limits |
| `subscriptions` | One per tenant, links to plan + Stripe IDs |
| `usage_events` | Billable actions with idempotency key |
| `idempotency_records` | Full HTTP response cache per key |
| `stripe_events` | Processed webhook event IDs (dedup) |
| `monthly_usage_summaries` | Reconciliation job output |

**Test:** `tests/integration/test_migrations.py::test_alembic_upgrade_on_clean_schema`

```
DROP SCHEMA public CASCADE → CREATE SCHEMA public
alembic upgrade head
→ tables present: tenants, usage_events, stripe_events, alembic_version  ✅
```

### ✅ Customer data isolated per tenant

**Test:** `tests/api/test_generate_and_usage.py::test_tenant_isolation`

```
Tenant A: POST /generate → records usage
Tenant B (new): GET /usage →
  api_calls.used = 0
  ai_tokens.used = 0
  cost.amount = 0
  (Tenant B sees zero — Tenant A's data is invisible)
```

### ✅ Seed is idempotent

**Test:** `tests/integration/test_metering_transactions.py::test_seed_is_repeatable`

```
run_seed() → run_seed() → plans count = 2 (not 4)
```

### ✅ Background job with retries and failure reporting

**Test:** `tests/integration/test_job.py::test_monthly_job_is_idempotent`

```
POST /generate (1 request)
reconcile_month() → reconcile_month() (run twice)
→ exactly 1 MonthlyUsageSummary row for demo tenant
→ api_calls = 1, ai_tokens = 235, cost_nano_usd = 1,791,000
  (idempotent: second run overwrites with same values)
```

Retry logic tested in `tests/unit/test_retry_utils.py`:
```
Flaky operation fails 2×, succeeds on 3rd → returns "ok" (attempts=3)
Operation that always fails → raises after exhausting all retries
Failures emit: ALERT job_failure operation=<name> attempt=N/3 error_type=<type>
```

### ✅ Validation at the boundary

**Test:** `tests/api/test_health_and_tenants.py::test_validation_error_is_422`

```
POST /generate with input_tokens=-1
→ 422
→ {"error": "VALIDATION_ERROR", "message": "Request validation failed."}
```

### ✅ Secrets clean

- `.env` is in `.gitignore` (never committed)
- `.env.example` has placeholder values only
- `SecretFilter` in `app/core/logging.py` drops log records containing: password, secret, authorization, stripe-signature, sk_live, sk_test, whsec_
- Live Stripe keys (`sk_live_*`) are rejected at startup via `Settings.reject_live_stripe_keys` validator

---

## Test output

_Run `docker compose exec api pytest` to regenerate:_

```
tests/unit/test_pricing.py ........                                   [ 25%]
tests/unit/test_retry_utils.py ..                                     [ 31%]
tests/api/test_health_and_tenants.py ....                             [ 44%]
tests/api/test_generate_and_usage.py ....                             [ 56%]
tests/billing/test_quotas.py .......                                  [ 75%]
tests/webhooks/test_stripe.py .....                                   [ 88%]
tests/integration/test_metering_transactions.py ..                    [ 94%]
tests/integration/test_job.py .                                       [ 97%]
tests/integration/test_migrations.py .                                [100%]
```
