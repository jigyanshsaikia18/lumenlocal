# Technical Architecture Document
## LumenLocal — Agency-First, GEO-Native GBP Platform

| | |
|---|---|
| **Document type** | Technical Architecture |
| **Version** | Draft v0.1 |
| **Status** | For review |
| **Companion docs** | `01_PRD.md`, `03_Phased_Roadmap.md`, `04_Database_Schema.md` |

---

## 1. Architectural Principles

1. **Multi-tenant, isolated by design.** One platform, strict tenant → client → location data isolation.
2. **Everything behind a flag.** The entitlement engine is core infrastructure, not a feature; new code ships flag-gated to satisfy the client-wise toggle requirement and safe rollout.
3. **Provider-abstracted.** Google APIs and AI-search providers sit behind internal abstraction layers so policy/provider changes don't ripple through the product.
4. **Async-first.** Geo-grid scans, AI-search sampling, listing sync, and report generation are queued background jobs, not request-path work.
5. **Compliance is a gateway, not a guideline.** No external write reaches a provider without passing the Policy Compliance Engine.
6. **Extensible by modules.** Capabilities are modules registered against the platform core, enabling the marketplace/plugin requirement.

---

## 2. High-Level System Diagram (logical)

```
                         ┌─────────────────────────────────────────────┐
                         │                CLIENT LAYER                  │
                         │  Web app (agency portal, white-label)        │
                         │  Client portal · Public API · MCP server     │
                         └───────────────┬─────────────────────────────┘
                                         │  (HTTPS / OAuth / API keys)
                         ┌───────────────▼─────────────────────────────┐
                         │              API GATEWAY / BFF               │
                         │  AuthN/Z · RBAC · Rate limiting · Tenant ctx │
                         └───────────────┬─────────────────────────────┘
                                         │
          ┌──────────────────────────────────────────────────────────────────────┐
          │                          CORE PLATFORM SERVICES                        │
          │                                                                        │
          │  Identity & RBAC   Entitlement/Flag   Billing &     Audit & Activity   │
          │  (SSO, 2FA)        Engine             Metering      Log                 │
          │                                                                        │
          │  Tenant/Client/Location Registry      Notification & Alerting          │
          └───────┬───────────────────────────────────────────────────┬───────────┘
                  │                                                     │
   ┌──────────────▼───────────────┐                  ┌──────────────────▼─────────────────┐
   │       DOMAIN MODULES         │                  │     POLICY COMPLIANCE ENGINE        │
   │  Dashboard/Insights          │  every external  │  (Policy Center rule-set, versioned)│
   │  Rank Tracking (geo-grid)    │  write routes ─► │  Validates replies/requests/posts/  │
   │  GEO / AI-Search Visibility  │  through here    │  listing edits before send. Blocks + │
   │  Listings & Citations        │                  │  logs violations.                   │
   │  Reviews & Reputation        │                  └──────────────────┬──────────────────┘
   │  Content / Posts / Media     │                                     │
   │  Profile Protection          │                  ┌──────────────────▼──────────────────┐
   │  Competitor Analysis         │                  │      INTEGRATION / PROVIDER LAYER     │
   │  Reporting                   │                  │  GBP API adapter (Account, Business   │
   │  AI Automation / Copilot     │                  │  Info, Reviews v4, Local Posts,       │
   └──────────────┬───────────────┘                  │  Performance)                         │
                  │                                   │  AI-Search providers (AI Overviews,   │
   ┌──────────────▼───────────────┐                  │  AI Mode, Gemini, ChatGPT, Perplexity,│
   │   ASYNC JOB / QUEUE LAYER     │ ◄──────────────► │  Grok)                                │
   │  Workers: scans, AI sampling, │                  │  Citation/Directory network           │
   │  sync, reports, monitoring    │                  │  Geocoding / Maps · LLM provider      │
   │  Scheduler (cron campaigns)   │                  │  Email/SMS gateway                    │
   └──────────────┬───────────────┘                  └──────────────────────────────────────┘
                  │
   ┌──────────────▼──────────────────────────────────────────────────────────────┐
   │                                DATA LAYER                                     │
   │  OLTP (relational, tenant-isolated)  ·  Time-series (rank/AI-visibility/perf) │
   │  Object store (media, report PDFs)   ·  Cache  ·  Search index  ·  Secrets    │
   │  Vault (OAuth tokens)  ·  Data warehouse (analytics/BI export)                │
   └──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Breakdown

### 3.1 Client layer
- **Agency web app** — primary SPA, white-label themed per tenant (logo, colors, domain).
- **Client portal** — scoped, read/approve-only experience for Client Owners.
- **Public API + Webhooks** — for agency integrations.
- **MCP server** — exposes core tools (scan, report, review, protection status) to agentic AI clients.

### 3.2 API Gateway / BFF
- Terminates auth, resolves **tenant context** on every request, enforces RBAC and rate limits, and injects entitlement checks. A Backend-for-Frontend shapes payloads per client app.

### 3.3 Core platform services
- **Identity & RBAC** — users, roles (incl. custom roles), SSO (SAML/OIDC), 2FA, session management. Permission model is capability-based (e.g., `reviews.reply`, `protection.reject_edit`).
- **Entitlement / Feature-Flag Engine** — the heart of the client-wise toggle requirement (see §4).
- **Tenant/Client/Location Registry** — the canonical hierarchy and the scoping authority for all data access.
- **Billing & Metering** — seat + per-location + credit packs; meters expensive ops (geo-grid, AI sampling, LLM tokens).
- **Audit & Activity Log** — append-only, immutable; records actor/action/target/before-after for every privileged or external-write action.
- **Notification & Alerting** — in-app, email, SMS, webhook; powers protection alerts and anomaly notifications.

### 3.4 Domain modules
Each PRD module maps to a service/module with its own data ownership, exposing internal APIs to the gateway and consuming the provider layer through adapters. The **GEO / AI-Search Visibility** module is the flagship and the heaviest consumer of the async + provider layers.

### 3.5 Policy Compliance Engine (gateway for all external writes)
- Loads the **active, versioned rule-set** from the Policy Center.
- Every reply, review-request, post, and listing edit is evaluated **before** the provider adapter is called.
- Hard-rule violations are **blocked** (not warned) and logged; soft issues are surfaced for human decision.
- Because guardrails are centrally versioned, a Super-Admin policy update propagates platform-wide immediately — the mechanism that satisfies "protect against frequent Google updates."

### 3.6 Integration / Provider layer
- **GBP API adapter** wraps the five active GBP API surfaces (Account Management, Business Information, **Reviews v4**, **Local Posts**, **Performance**). Encapsulates Google's write limits (e.g., reviews are reply-only) so no module can violate them.
- **AI-Search provider abstraction** — a uniform interface over AI Overviews, AI Mode, Gemini, ChatGPT, Perplexity, Grok; normalizes their heterogeneous responses into mention/prominence/citation records. New providers plug in here.
- **Citation/Directory network adapter**, **Geocoding/Maps**, **LLM provider** (for drafting/analysis), **Email/SMS gateway**.

### 3.7 Async job / queue layer
- Workers for: geo-grid scans, AI-search sampling, listing sync, citation submission, report generation, and 24/7 profile-change monitoring.
- **Scheduler** runs recurring campaigns/scans and cron-based monitoring.
- Backpressure, retries, idempotency, and per-tenant quota fairness are first-class.

### 3.8 Data layer
- **OLTP relational store** — tenants, clients, locations, users, roles, entitlements, campaigns, content, audit. Tenant isolation enforced at the data-access layer.
- **Time-series store** — rank history, AI-visibility history, performance metrics, change events (high write volume).
- **Object store** — media, generated report PDFs.
- **Cache** — hot dashboard data, provider response caching where permitted.
- **Search index** — fast lookup across locations/reviews/competitors.
- **Secrets vault** — OAuth refresh tokens and provider credentials, encrypted, access-audited.
- **Data warehouse** — analytics, cohorting, and BI export connectors.

---

## 4. The Entitlement / Feature-Flag Engine (deep dive)

The single most architecturally important platform service, because it underpins the agency-first, client-wise toggle requirement.

**Resolution order (most specific wins):**
```
Location override  >  Client (sub-account)  >  Plan/Tier  >  Platform default
```

**Data model (conceptual):**

| Entity | Key fields |
|---|---|
| `feature` | key, name, description, dependencies[], default_state |
| `plan_feature` | plan_id, feature_key, state |
| `client_feature` | client_id, feature_key, state, set_by, set_at |
| `location_feature` | location_id, feature_key, state, set_by, set_at |
| `entitlement_change_log` | who/what/when/before/after |

**Enforcement points (defense in depth):**
1. **UI** — feature hidden/disabled if off for the resolved scope.
2. **API gateway** — returns `403 feature_disabled` for disabled capabilities.
3. **Job layer** — scheduled jobs check entitlement before running; disabled features pause cleanly.
4. **Reporting** — disabled modules are excluded from generated reports.

**Behaviors:**
- Dependency resolver prevents inconsistent states (enabling a dependent feature auto-prompts to enable its prerequisite).
- "What this client sees" preview renders the resolved entitlement set for any client/role/location.
- Sub-second effect after change; no deploy.

---

## 5. Key Data Flows

### 5.1 Geo-grid + AI-Search (GEO) scan
```
Operator triggers scan (or scheduler fires)
  → entitlement check (geo-grid / GEO enabled for this location?)
  → credit check & reservation
  → job enqueued with grid coords + prompt set
  → workers fan out:
       • classic rank: query map/organic per grid point
       • GEO: send prompts to each AI provider per grid point, repeated N times
  → provider abstraction normalizes responses → mention/prominence/citation records
  → results written to time-series store; SoLV + AI-Visibility (SAIV) computed
  → recommendation engine derives prioritized actions
  → dashboard + report data updated; copilot can summarize
```

### 5.2 Review reply (compliance-gated write)
```
Operator/AI drafts reply
  → Policy Compliance Engine evaluates (incentive language? staff-name? pressure?)
       • hard violation → BLOCK + explain + log
       • clean → proceed
  → approval gate (if Approval mode) or auto (if Autopilot bounded)
  → GBP Reviews v4 adapter posts reply (reply-only enforced)
  → audit log written
```

### 5.3 Profile-change monitoring (protection)
```
Scheduler polls GBP Business Information per monitored location
  → diff against last-known snapshot across 20+ critical fields
  → change detected → severity classified (e.g., map-pin move = high)
  → near-real-time alert to operator/client (in-app/email/SMS)
  → one-click reject/restore action → GBP adapter
  → change correlated with rank/AI-visibility timeline
```

---

## 6. Compliance Architecture (requirements #10 & #11)

- **Policy Center** — Super-Admin-managed, versioned rule-set (Google policy + FTC rule) expressed as machine-evaluable rules. Versioning enables instant platform-wide propagation on Google updates.
- **Compliance Engine as mandatory gateway** — structurally impossible for a module to write to a provider without passing it.
- **Structural prohibitions** — review-request flows have no sentiment-routing branch; composers lint for incentive/staff-name/pressure language; reviews are reply-only by adapter contract; the connection flow respects Google's project-ownership rule.
- **Auditability** — every external write and every blocked violation is logged, providing the evidence trail that is itself a selling point.

---

## 7. Security & Multi-Tenancy
- Tenant context is mandatory on every request; data-access layer rejects cross-tenant queries.
- OAuth tokens stored in a secrets vault; scoped, rotated, access-audited.
- Encryption in transit (TLS) and at rest.
- Least-privilege service-to-service auth; per-tenant rate limits.
- 2FA enforceable per tenant; SSO for enterprise agencies.
- SOC 2 readiness and optional data-residency are roadmap targets.

---

## 8. Scalability & Reliability
- Stateless app tier scales horizontally behind the gateway.
- The heavy load is **scan/sampling**; isolate it in autoscaling worker pools with per-tenant fairness so one large agency can't starve others.
- Provider failures degrade gracefully (e.g., one AI provider down → GEO score computed from available providers, flagged as partial).
- Idempotent jobs + retries + dead-letter queues; circuit breakers around provider calls.
- 99.9% app-tier availability target.

---

## 9. Extensibility (requirement #14)
- **Module registry** — new capabilities register against the core and ship behind flags.
- **Public API + webhooks + MCP** as first-class integration surfaces.
- **Provider abstraction** lets new AI-search engines or directory networks plug in without touching modules.
- **Marketplace** path: third-party or internal modules distributed and toggled per client through the same entitlement engine.

---

## 10. Technology Selection — Recommended Concrete Stack

A concrete, sensible default stack is recommended below (adopted and extended from the LocateX blueprint) so teams can start immediately. The architecture remains portable — anything here can be swapped via ADR — but these are the defaults the rest of the docs assume.

| Concern | Recommended choice | Why |
|---|---|---|
| Frontend | **Next.js (App Router) + TypeScript + Tailwind** | Fast SSR/ISR, clean white-label theming, strong ecosystem |
| Backend API | **FastAPI (Python 3.11+)** | Async-friendly for heavy data transformation; pairs naturally with the worker layer |
| OLTP | **PostgreSQL 15+** (with `JSONB` for flexible profile/feature data) | Strong consistency for hierarchy/entitlements; `JSONB` fits feature_gates + profile snapshots |
| Queue / workers | **Redis + Celery** | Async fan-out for geo-grid + AI sampling, scheduled monitoring, report compilation |
| Time-series | Purpose-built TS store (or Postgres + partitioning to start) | High-volume rank/AI-visibility/performance history |
| Object store | Cloud object storage | Media + report PDFs |
| Secrets | Managed vault | OAuth token safety, audited access |
| Search | Managed search index | Cross-entity lookup |
| LLM / AI-search | Provider-abstracted | Avoid lock-in; cost control for GEO |

> The full table/column schema lives in `04_Database_Schema.md`. Lock remaining choices in ADRs during Phase 0.
