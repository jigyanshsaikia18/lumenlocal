# CLAUDE.md — LumenLocal project memory

> Copy this file to your **repo root** as `CLAUDE.md`. Claude Code loads it every session. Keep it tight; when Claude does something wrong, add a rule here so it doesn't repeat. For deep detail, point to `/docs`.

## What we're building
Agency-first, **GEO-native** multi-tenant SaaS for Google Business Profile (GBP) optimization. Agencies manage many clients' profiles. Headline differentiator: **AI-search/GEO visibility**. Core principle: **compliant by architecture**. Full spec in `/docs` (start with `/docs/00_START_HERE.md`).

## Stack
- Backend: **FastAPI** (Python 3.11+), Poetry. Async where it matters.
- Frontend: **Next.js (App Router) + TypeScript + Tailwind**.
- DB: **PostgreSQL 15+** (JSONB for flexible fields). ORM: SQLAlchemy + Alembic migrations.
- Jobs: **Redis + Celery** for scans/sampling/reports/monitoring.
- Tests: **pytest** (backend), **vitest + React Testing Library** (frontend), **Playwright** (E2E).

## Where things live
- Specs: `/docs/01_PRD.md` … `/docs/08_Test_Strategy.md`
- DB schema: `/docs/04_Database_Schema.md` — follow it exactly; don't invent columns.
- API contract: `/docs/05_API_Specification.md` — match paths, status codes, middleware order.
- Tickets: `/docs/06_Backlog_Epics_and_Stories.md` — work one ticket per session.
- Backend code: `backend/app/...` · Frontend: `frontend/src/...`

## How to work (DO)
- **Plan first** for non-trivial tasks (Plan Mode), then implement in small steps.
- **One ticket at a time.** Read the ticket's referenced docs before coding.
- **Write tests with the code.** A ticket isn't done until its tests pass (`08_Test_Strategy.md`).
- **Run** `pytest` / `vitest` before saying a task is complete.
- **Tenant-scope every query.** Resolve tenant → role → entitlement → quota → (policy) → handler.
- **Commit on a feature branch** with a clear message after each ticket.
- Keep diffs focused; prefer `Edit` over rewriting whole files.

## Hard rules — COMPLIANCE (do NOT violate; this is why the product is safe to sell)
- **NO review gating.** Never add any field, branch, or flow that routes review requests by predicted sentiment or diverts unhappy customers. Campaigns are `equal_all` only.
- **NO incentivized-review tooling.** Lint and block incentive language (free/discount/coupon/gift/raffle) and staff-name solicitation in replies/requests.
- **Reviews are reply-only.** Never write code that claims to create/edit/delete customer reviews or ratings — the Google API forbids it.
- **NO silent auto-revert.** Profile protection = detect + alert + one-click/bounded revert. Do NOT build unsupervised timer-based corrective writes to critical fields (name/category/phone/pin). Respect `revert_mode`.
- **NO detection-evasion.** Rate-limit/stagger critical-field edits as legitimate change-management; never frame it as disguising automation as "organic."
- **Every external write to Google passes the Policy Compliance Engine first** (returns 422 on violation). No module may bypass it.
- **Respect Google's project-ownership rule** in connection flows.
- **Enforce `audit_log` immutability at the DB level** (revoke UPDATE/DELETE), not just by convention. Handle review/customer **PII** per GDPR/CCPA (retention + erasure). See `/docs/01_PRD.md §11.1` for open caveats (scanning ToS, data retention) — don't claim "fully compliant" for geo-grid/GEO scanning.

## Don'ts (general)
- Don't store raw OAuth tokens in Postgres — only `token_ref` to the vault.
- Don't run destructive shell commands (`rm -rf`, `DROP`, force-push) without explicit approval.
- Don't disable failing tests to make a build pass — fix the cause.
- Don't put real secrets in code, fixtures, or `.env` committed to git.
- Don't add features outside the current ticket's scope.

## Model guidance (switch with /model)
- **Opus 4.8** — architecture, the entitlement resolver, the compliance engine, hard async/debugging, plan-mode reasoning.
- **Sonnet 4.6** — default for most implementation (CRUD, UI, models, routine endpoints).
- **Haiku 4.5** — boilerplate, simple edits, test scaffolds, quick lookups.

## Commit/PR convention
- Branch: `phaseN/<ticket-id>-short-desc` (e.g. `phase2/p2c-2-geo-scan-worker`).
- Conventional commits: `feat: …`, `fix: …`, `test: …`, `chore: …`.
