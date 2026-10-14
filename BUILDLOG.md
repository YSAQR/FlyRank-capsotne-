# BUILDLOG

Honest record of AI-assisted development for the FlyRank metering & billing capstone.

## Phase 0 — Inspection (2026-10-15)

- Workspace `d:\trib` is an existing Git repo containing unrelated projects (`FlyRank` CRUD tasks, `chatBot`, `polite-book-scraper`). Those files were **not** modified or deleted.
- No capstone PDF was present on disk in the workspace, Downloads, or Desktop. The implementation follows the full written brief in the task message.
- Git 2.55 is available. GitHub CLI (`gh`) is **not** installed. GitHub auth could not be verified.
- Local Python: `C:\Users\yasso\.local\bin\python3.14.exe` (3.14.6). Docker 29.6.2 and Compose v5.3.1 are available.
- Decision: create a **sibling** directory `d:\flyrank-capstone-metering-billing` so the capstone is not nested inside another project.

## Phase 1 — Design

- Wrote `docs/design.md`, `docs/architecture.md`, `docs/requirements-checklist.md`.
- Chosen defaults (documented, not silent):
  - Pro quotas: 100,000 API calls / 10,000,000 AI tokens per period.
  - Money: integer nano-USD.
  - Dev identity: `X-Tenant-Id` + `X-Dev-Token`.
  - Billing period: Stripe period if set, else UTC calendar month.
  - `/generate` `input_tokens` = fresh input tokens.
  - Quota concurrency: `SELECT … FOR UPDATE` on the subscription row.
- AI assistance: drafted design text from the brief. No code generated yet in this phase.

## Known issues / manual steps

- Public GitHub repo creation is blocked until `gh` is installed and authenticated (or the user creates the repo in the GitHub UI).
- Stripe Checkout live evidence needs test-mode keys and Stripe CLI; ordinary pytest uses mocks.
