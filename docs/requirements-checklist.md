# Requirements checklist

Source of truth: FlyRank Internship Backend Track Capstone — Usage Metering & Billing Engine (task brief). Status is updated as work lands.

| ID | Requirement | Status |
| --- | --- | --- |
| R1 | FastAPI + Python 3.12+ + PostgreSQL + SQLAlchemy 2 + Alembic + Pydantic + pytest/HTTPX + Docker Compose | IN PROGRESS |
| R2 | Layered architecture (HTTP / services / persistence) | IN PROGRESS |
| R3 | Tenant, Plan, Subscription, UsageEvent with constraints and indexes | IN PROGRESS |
| R4 | Free plan 1,000 API / 100,000 tokens; documented Pro limits | IN PROGRESS |
| R5 | Dev-only tenant identity; no production-auth claim | IN PROGRESS |
| R6 | Tenant isolation on all tenant-scoped APIs | IN PROGRESS |
| R7 | Idempotent metering via DB uniqueness + conflict handling | IN PROGRESS |
| R8 | Conflicting idempotency payload → client error | IN PROGRESS |
| R9 | Concurrent duplicate keys do not double-count | IN PROGRESS |
| R10 | Atomic quota check + record; no overspend | IN PROGRESS |
| R11 | Quota boundaries including exact limit and concurrent remainder | IN PROGRESS |
| R12 | 429 quota exhausted; 402 billing/payment required; documented split | IN PROGRESS |
| R13 | POST /generate dummy billable AI endpoint with Idempotency-Key | IN PROGRESS |
| R14 | Integer token pricing: fresh, cached, output, reasoning | IN PROGRESS |
| R15 | GET /usage monthly summary with cost vs quantity | IN PROGRESS |
| R16 | Stripe TEST Checkout + signed webhooks + event ID uniqueness | IN PROGRESS |
| R17 | Background job with retries and failure reporting | IN PROGRESS |
| R18 | Seed command idempotent; Alembic migrations | IN PROGRESS |
| R19 | README, capstone.yaml, EVIDENCE.md, BUILDLOG.md, design, architecture | IN PROGRESS |
| R20 | Dedicated public GitHub repo `flyrank-capstone-metering-billing` | BLOCKED (`gh` not installed) |

## Acceptance probes

| Probe | Description | Status |
| --- | --- | --- |
| P1 | Same billable request twice, same key → one usage event | PENDING tests |
| P2 | Quota boundaries; over-limit returns documented status | PENDING tests |
| P3 | Stripe test Checkout + verified webhook updates plan/limits | BLOCKED without live Stripe test keys |
| P4 | Forged webhook 400; replay does not repeat side effects | PENDING tests (signature via Stripe test helper / mocks) |
| P5 | Cached + reasoning pricing exact; GET /usage matches | PENDING tests |
