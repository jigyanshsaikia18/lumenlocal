# Backlog — Epics, User Stories & Build Tickets

| | |
|---|---|
| **Document type** | Engineering Backlog |
| **Version** | Draft v0.1 |
| **How to use** | One **ticket = one Claude Code work session.** Build in phase order (`03_Phased_Roadmap.md`). |
| **Ticket format** | `ID — title` · *As a … I want … so that …* · **Acceptance:** testable conditions |

> Tickets are intentionally small. If a ticket feels big, ask Claude Code to split it. Each ticket references the docs it should read first.

---

## PHASE 0 — Foundations

**EPIC P0 · Project setup**
- **P0-1 — Monorepo scaffold.** *As a developer I want the repo structure so that backend/frontend/infra coexist.* **Acceptance:** `backend/` (FastAPI+Poetry), `frontend/` (Next.js+TS+Tailwind), `docker-compose.yml` (Postgres 15, Redis), `/docs` with these files, root `CLAUDE.md`. `docker compose up` starts Postgres+Redis.
- **P0-2 — CI skeleton.** **Acceptance:** lint + test workflow runs on push; backend `pytest` and frontend `vitest` jobs exist (even if empty).
- **P0-3 — Env & secrets convention.** **Acceptance:** `.env.example`, settings loader, no secrets committed; token vault interface stubbed.

---

## PHASE 1 — Agency Spine

**EPIC P1A · Multi-tenancy & data layer** *(reads `04_Database_Schema.md`)*
- **P1A-1 — Core models + migrations.** Tables: `tenants`, `clients`, `users`, `user_roles`, `role_permissions`, `plans`. **Acceptance:** SQLAlchemy models + Alembic migration; models import clean; tenant_id FK present.
- **P1A-2 — Tenant isolation guard.** **Acceptance:** every query is tenant-scoped; a unit test proves cross-tenant reads are impossible (consider Postgres RLS).

**EPIC P1B · Identity & RBAC** *(reads `05_API_Specification.md` §2–3)*
- **P1B-1 — Auth (login/refresh/logout, JWT, bcrypt).** **Acceptance:** endpoints work; passwords hashed; `/me` returns roles.
- **P1B-2 — RBAC middleware.** **Acceptance:** capability checks (`reviews.reply` etc.); 403 on out-of-scope; custom-role scaffold; tests for each role.
- **P1B-3 — SSO + 2FA scaffold.** **Acceptance:** SAML/OIDC hook points + optional 2FA flag (can stub provider).

**EPIC P1C · Entitlement / feature-toggle engine** *(the differentiator — reads PRD §5)*
- **P1C-1 — Feature registry + resolution.** **Acceptance:** `features`, `plan_features`, `client_features`, `location_features`; resolver returns correct on/off with **location > client > plan > default** precedence; dependency validation; unit tests cover all 4 levels.
- **P1C-2 — Entitlement enforcement at gateway.** **Acceptance:** disabled feature → `403 feature_disabled`; toggling takes effect < 1 min; change is audit-logged.
- **P1C-3 — "What this client sees" preview + admin UI.** **Acceptance:** preview endpoint + a Super-Admin screen to toggle per client/location.
- **P1C-4 — Usage quotas + counters.** **Acceptance:** Super-Admin caps on api_calls/scans/llm_credits; metered op pauses at cap with alert; `/usage` reflects consumption.

**EPIC P1D · GBP connection** *(reads PRD §6 + compliance §9)*
- **P1D-1 — OAuth self-connect.** **Acceptance:** consent URL → callback → token vaulted (only `token_ref` in DB); locations importable.
- **P1D-2 — Agency-proxy connect + bulk import.** **Acceptance:** agency-on-behalf flow; CSV/batch import; respects Google project-ownership rule.
- **P1D-3 — Token health monitor.** **Acceptance:** background worker flags expiring/disconnected tokens; alert fired.

**EPIC P1E · Premium dashboard v1** *(reads `08_Test_Strategy.md`; frontend-design skill)*
- **P1E-1 — Health score + performance widgets.** **Acceptance:** dashboard shows health grade + last-30-day metrics from Performance API; white-label themed.
- **P1E-2 — Multi-location command center.** **Acceptance:** map + filters + roll-up KPIs; respects entitlements (hidden if off).
- **P1E-3 — Audit log + billing scaffold.** **Acceptance:** immutable `audit_log` writes on privileged actions; credit metering scaffold.

---

## PHASE 2 — GEO + Classic Rank (completes MVP)

**EPIC P2A · Async/queue layer**
- **P2A-1 — Celery + Redis job framework.** **Acceptance:** enqueue/track/retry; per-tenant fairness; dead-letter queue; idempotent tasks.

**EPIC P2B · Classic rank tracking**
- **P2B-1 — Geo-grid math + scan worker.** **Acceptance:** given center+radius+dimensions, compute coords; query per node; store `geogrid_scans` with SoLV; unit test the coordinate math.
- **P2B-2 — Keyword rank tracker.** **Acceptance:** map+organic, mobile/desktop, scheduled runs, credit-metered.
- **P2B-3 — Rank trend + heatmap UI.** **Acceptance:** grid heatmap (colored by rank) + history chart.

**EPIC P2C · GEO / AI-search visibility (flagship)** *(reads PRD Module 3)*
- **P2C-1 — AI-search provider abstraction.** **Acceptance:** uniform interface over AI Overviews/AI Mode/Gemini/ChatGPT/Perplexity/Grok; normalizes responses to mention/prominence/citation records; new provider pluggable.
- **P2C-2 — GEO scan worker (geo-grid-for-AI).** **Acceptance:** samples prompts across grid + repeated runs; computes SAIV; stores `geo_ai_scans` incl. `cited_sources`.
- **P2C-3 — AI-readiness audit + recommendation engine.** **Acceptance:** scores GEO signals (category, services, NAP, reviews, photos, Q&A); returns prioritized actions.
- **P2C-4 — Prompt library.** **Acceptance:** niche-aware defaults + custom prompts (`geo_prompts`).
- **P2C-5 — GEO dashboard + competitor AI-share overlay.** **Acceptance:** SAIV trend, per-provider breakdown, cited sources, competitor comparison on grid.

---

## PHASE 3 — Reputation, Content & Compliance Gateway

**EPIC P3A · Policy Compliance Engine** *(build BEFORE the write features below — reads PRD §9)*
- **P3A-1 — Policy Center (versioned rulesets).** **Acceptance:** `policy_rulesets` CRUD; publishing a version propagates platform-wide; `compliance_events` logged.
- **P3A-2 — Compliance gateway.** **Acceptance:** every external write passes the engine; hard violations **blocked (422)** with rule + ruleset_version; cannot be bypassed by any module.

**EPIC P3B · Reviews & reputation**
- **P3B-1 — Review inbox (reply-only).** **Acceptance:** list reviews; reply via Reviews v4; no create/edit/delete paths exist.
- **P3B-2 — AI reply drafting + reply linting.** **Acceptance:** draft endpoint; incentive/staff-name/pressure language blocked.
- **P3B-3 — Equal-send review campaigns.** **Acceptance:** only `equal_all` mode; **no sentiment-routing field exists** (test asserts absence).
- **P3B-4 — Sentiment/theme analysis + review widget.** **Acceptance:** themes summary; embeddable schema-rich widget.

**EPIC P3C · Content, posts & media**
- **P3C-1 — Post scheduler + content calendar.** **Acceptance:** standard/offer/event/recurring; bulk CSV.
- **P3C-2 — AI content gen + local-context ingestion.** **Acceptance:** injects landmarks/cross-streets/local phrasing; passes pre-publish check.
- **P3C-3 — Media management + Vision/policy pre-check.** **Acceptance:** bulk upload, descriptive naming; non-compliant blocked.
- **P3C-4 — Q&A + Products/Services.** **Acceptance:** CRUD + publish.

---

## PHASE 4 — Protection, Competitors, Reporting

**EPIC P4A · Profile protection**
- **P4A-1 — Change monitoring (20+ fields) + baseline.** **Acceptance:** worker diffs live vs `profile_data_locked`; severity classified; near-real-time alert.
- **P4A-2 — Bounded revert + suggested-edit reject.** **Acceptance:** `revert_mode` (`alert_only` default / `auto_revert_critical` / `off`); one-click restore; NO silent timer-based critical-field writes; rate-limited + audited.
- **P4A-3 — Suspension-risk monitor + reinstatement assistant.** **Acceptance:** risk signals + guided workflow.
- **P4A-4 — Algorithm/Policy update tracker.** **Acceptance:** Super-Admin feed wired into Policy Center.

**EPIC P4B · Competitor analysis**
- **P4B-1 — Discovery + benchmark (incl. AI-share).** **P4B-2 — Geo-grid competitor overlay + gap/distance analysis.**

**EPIC P4C · Reporting**
- **P4C-1 — Drag-and-drop report builder.** **P4C-2 — Scheduled monthly/quarterly/yearly white-label PDFs + live links.** **P4C-3 — AI-narrated summaries.** **Acceptance:** reports omit toggled-off modules, respect RBAC.

---

## PHASE 5 — AI Automation, Listings, Extensibility

**EPIC P5A · AI automation**
- **P5A-1 — Copilot (NL over scope).** **P5A-2 — Approval/Autopilot recipes (per-client toggle, all writes through Policy Engine).**

**EPIC P5B · Listings & citations**
- **P5B-1 — NAP scanner + citation audit.** **P5B-2 — Multi-directory sync.** **P5B-3 — Duplicate detection/suppression.**

**EPIC P5C · Extensibility**
- **P5C-1 — Public REST API + webhooks.** **P5C-2 — MCP server exposing core tools.** **P5C-3 — Module/marketplace + flag-gated plugins.**

---

## PHASE 6 — Enterprise & Channels
- **P6-1 — SSO depth + SOC 2 controls.** **P6-2 — Data residency options.** **P6-3 — Apple Business Connect / Bing Places.** **P6-4 — Cost/quota governance + packaging experiments.**

---

## Definition of Done (every ticket)
1. Code matches the relevant doc (PRD/API/Schema).
2. Unit tests written and passing (see `08_Test_Strategy.md`).
3. Lint/format clean.
4. Entitlement + RBAC respected (if user-facing).
5. Any external write passes the Policy Engine.
6. Audit log written (if privileged).
7. Committed on a feature branch with a clear message.
