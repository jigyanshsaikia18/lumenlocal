# Product Requirements Document (PRD)
## Working title: **LumenLocal** — Agency-First, GEO-Native Google Business Profile Platform

| | |
|---|---|
| **Document type** | Product Requirements Document |
| **Version** | Draft v0.1 |
| **Status** | For review |
| **Positioning** | Agency-first SaaS · Client-wise feature-toggle engine · AI-Search / GEO-native |
| **Owner** | Product |
| **Related docs** | `02_Technical_Architecture.md`, `03_Phased_Roadmap.md`, `04_Database_Schema.md` |

> *LumenLocal is a placeholder name used for readability — rename freely.*

---

## 1. Executive Summary

LumenLocal is an enterprise-grade, multi-tenant SaaS platform that lets **agencies** manage, optimize, protect, and report on the **Google Business Profiles (GBP)** of their clients at scale — across any business niche.

It is differentiated on two pillars:

1. **GEO-native (Generative Engine Optimization).** Local discovery is shifting from the classic map pack to AI-generated answers. Google now uses GBP data as a structured input for its Gemini-powered AI Overviews, meaning the same profile that wins a map-pack slot is also the one cited in AI answers. LumenLocal treats *AI-search visibility* (Google AI Overviews, AI Mode, Gemini, ChatGPT, Perplexity, Grok) as a first-class, measured, optimizable surface — not an afterthought bolted onto a legacy rank tracker.
2. **Compliance-by-architecture.** Google's 2026 review-policy crackdown and the FTC Consumer Review Rule made many common "growth" tactics (review gating, incentivized reviews, staff-name solicitation, on-premise review pressure) into suspension-and-fine risks. LumenLocal makes the compliant path the *only* path the product offers, turning policy safety into a sellable feature instead of a liability.

The platform is built **agency-first**: white-label, multi-client hierarchy, credit/seat/location billing, and — critically — a **client-wise feature-toggle engine** that lets a Super Admin or Agency Admin switch any capability on or off per individual client, plan, or location.

---

## 2. Problem Statement

**For agencies managing local SEO across many clients today:**

- Capabilities are fragmented across 4–6 tools (rank tracking, listings/citations, reviews, posting, reporting), each billed separately and none aware of the others.
- Almost no tool measures or optimizes for **AI-search visibility**, even though that is where local discovery is moving.
- Profiles get silently altered — by competitors, customers, third-party tools, or Google's own AI — and rankings drop before anyone notices.
- A single non-compliant review tactic can now trigger **mass review removal, profile suspension, and FTC penalties**, yet most tools provide no guardrails.
- Reporting is manual, time-consuming, and rarely white-labeled cleanly across dozens of locations.
- Agencies cannot easily tailor *which* features each client sees, so they over-provision (cost) or maintain multiple tool stacks (complexity).

**LumenLocal collapses this into one governed, white-label platform where every automation is policy-bounded and AI-search is a measured surface.**

---

## 3. Goals, Non-Goals & Success Metrics

### 3.1 Product Goals
- G1 — Be the single platform an agency needs to run GBP for all clients (consolidation).
- G2 — Make AI-search/GEO visibility measurable and improvable (differentiation).
- G3 — Prevent profile damage and policy violations before they happen (protection & trust).
- G4 — Let agencies tailor the product per client without engineering work (feature-toggle engine).
- G5 — Cut agency reporting time dramatically via scheduled, white-label, AI-narrated reports.

### 3.2 Non-Goals (for v1)
- Building a full social-media management suite (only GBP posting is in scope).
- Paid-ads management (Google Ads/LSAs) — integration only, not management.
- Website CMS / page building.
- Acting as the client's GBP API project owner in violation of Google's prohibition (see §11).

### 3.3 Success Metrics (North Star + supporting)

| Tier | Metric | Target signal |
|---|---|---|
| **North Star** | Net locations under active management | Compounding growth MoM |
| Activation | % of new client locations reaching "fully connected + first scan" within 48h | ≥ 80% |
| Differentiation | % of managed locations with AI-Search Visibility (SAIV-equivalent) tracked | ≥ 60% by month 6 |
| Retention | Agency logo retention (annual) | ≥ 90% |
| Protection | Median time-to-alert on unauthorized profile change | < 60 min |
| Efficiency | Median time to generate a multi-location client report | < 2 min |
| Compliance | Policy violations *blocked* by the platform per 1k actions | Tracked, trending down as users learn |

---

## 4. Target Users, Personas & Roles

### 4.1 Buyer & primary user
**Local SEO / digital agencies** (1–500 clients) who resell GBP management. Secondary: in-house teams at multi-location brands (served via the same toggle engine).

### 4.2 Personas

| Persona | Role in product | Primary jobs-to-be-done |
|---|---|---|
| **Super Admin** (platform operator / agency owner) | Full control | Configure tenants, toggle features per client, set policy guardrails, manage billing, white-label |
| **Agency Admin** | Org-level admin within a tenant | Manage account managers, assign clients, configure per-client features (delegated), oversee compliance |
| **Account Manager** | Day-to-day operator | Run scans, draft posts/replies, action recommendations, generate reports for assigned clients |
| **Client Owner** | The end business | View dashboard, approve actions (if approval mode on), see reports — scoped to their own locations only |
| **Analyst / Viewer** | Read-only | View dashboards and reports; no edits |

### 4.3 Role-Based Access Control (RBAC) — requirements

- RBAC-1: Roles are hierarchical; higher roles inherit lower-role read access within their scope.
- RBAC-2: Access is scoped by tenant → sub-account (client) → location. A Client Owner can never see another client's data.
- RBAC-3: Support **custom roles** (Super Admin can define permission sets) for future flexibility.
- RBAC-4: Every permission maps to a granular capability (e.g., `reviews.reply`, `posts.publish`, `protection.reject_edit`, `reports.schedule`).
- RBAC-5: All privileged actions are written to an immutable audit log (actor, action, target, timestamp, before/after).
- RBAC-6: Support SSO (SAML/OIDC) for enterprise agencies and optional 2FA enforcement per tenant.

---

## 5. The Client-Wise Feature-Toggle Engine (named requirement — flagship platform capability)

This is a core differentiator and must be treated as a first-class product, not a config file.

### 5.1 Concept
A centralized **entitlement system** where a Super Admin (and, by delegation, an Agency Admin) can enable/disable any feature at four resolution levels, with the most specific winning:

```
Platform default  →  Plan/Tier  →  Client (sub-account)  →  Location
   (broadest)                                                (most specific)
```

### 5.2 Functional requirements

- FT-1: Every user-facing capability is registered as a **feature flag** with a stable key, display name, description, and dependency list.
- FT-2: Super Admin can toggle any flag **per client** and **per location** from an admin console, with effect in < 1 minute (no deploy).
- FT-3: Toggling a feature **off** hides its UI, disables its APIs, pauses its background jobs, and excludes it from reports for that scope — cleanly, with no broken links.
- FT-4: Flags support **dependencies** (e.g., "AI reply drafting" requires "Review inbox") and the engine prevents inconsistent states.
- FT-5: Flags can be bound to **billing plans** so that selling a tier automatically provisions the right feature set, while still allowing per-client overrides.
- FT-6: Changes to entitlements are audit-logged and optionally require Agency Admin approval.
- FT-7: A read-only **"What this client sees" preview** lets an operator view the product exactly as a given client/role/location would.
- FT-8: The engine exposes an internal API so new features ship behind a flag by default (supports staged rollout and the extensibility requirement).
- FT-9: **Per-scope usage quotas (Super-Admin caps).** Beyond on/off flags, the Super Admin can set hard monthly limits per tenant/client on the expensive operations: Google API calls, geo-grid/AI scans, and AI/LLM credits. When a cap is hit, the affected jobs pause gracefully (not error-storm), the operator is alerted, and an overage/upgrade path is offered. *(Adopted from LocateX's API-quota concept, generalized into the entitlement engine so it composes with feature flags rather than living separately.)*

### 5.3 Acceptance criteria
- A Super Admin can turn off "Geo-grid scanning" for Client A's single location and confirm: the menu item disappears for that client, scheduled scans pause, the API returns `403 feature_disabled`, and the next report omits the section — all without affecting Client B.

---

## 6. GBP Connection & Onboarding Flows (named requirement)

Two connection paths must coexist:

### 6.1 Client self-connect (OAuth)
- ON-1: Client authenticates via Google OAuth and grants the platform access to the locations they manage.
- ON-2: Platform imports locations, verifies management access, and runs an initial health audit + first scans automatically.

### 6.2 Agency/Super-Admin connect on the client's behalf
- ON-3: An operator can initiate connection where the client grants access (via a guided, link-based flow) without needing to navigate Google themselves — reducing SMB onboarding friction.
- ON-4: Where the agency already has manager access on the client's GBP, locations can be imported directly.

### 6.3 Compliance constraint (hard)
- ON-5: **The platform must require each agency/end-client's programmatic GBP usage to run under their own Google Business Profile project where Google's policy requires it.** The product must not architect a flow that lets clients avoid applying for their own project in violation of Google's API policy. (See `02_Technical_Architecture.md` §Compliance, and §11 below.)

### 6.4 Onboarding outcomes
- ON-6: A "connection health" indicator shows token validity, scope coverage, and re-auth prompts before access lapses.
- ON-7: Bulk connect/import for multi-location clients (CSV + OAuth batch).

---

## 7. Functional Requirements by Module

> Modules are grouped. **Module 3 (AI-Search/GEO) is the flagship** given the chosen positioning and is specified in the most depth.

### Module 1 — Premium Dashboard & Insights

**Goal:** Give the real, at-a-glance picture of each profile (requirement: premium, worthy dashboard).

- D-1: **Profile Health Score** — real-time completeness + optimization grade per location, with the specific gaps driving the score.
- D-2: **Performance metrics** from the GBP Performance API — calls, website clicks, direction requests, searches (branded/discovery), views — with period comparisons.
- D-3: **Multi-location command center** — map view, filters, and roll-up KPIs across a client's full portfolio.
- D-4: **Customizable widget layout** — drag/drop, role- and client-specific dashboards.
- D-5: **Anomaly & trend alerts** — sudden drops in views/calls/rank/AI-visibility trigger proactive notifications.
- D-6: All dashboard sections respect the feature-toggle engine (hidden if disabled for that client).

*Acceptance:* For a connected location, the dashboard loads health score, last-30-day performance metrics, and current rank/AI-visibility snapshot in a single view, branded per the agency's white-label theme.

### Module 2 — Local Rank Tracking (classic map/organic)

- RT-1: **Geo-grid rank tracking** — simulate searches across a configurable coordinate grid (multiple grid sizes), producing a Share-of-Local-Voice (SoLV-equivalent) metric and a heatmap.
- RT-2: **Keyword rank tracker** — map pack + organic, mobile/desktop, multiple keywords per location, scheduled runs.
- RT-3: **Historical trends & action correlation** — overlay rank changes against actions taken and profile changes (ties into Module 7 protection log).
- RT-4: Scheduled/automated scans with credit metering.

### Module 3 — **AI-Search Visibility / GEO (FLAGSHIP)**

**Why this is the headline:** Ranking on Google and being cited in AI answers are now two different games; a profile can sit on page one and never be cited by AI Overviews, ChatGPT, or Gemini. GEO targets **inclusion in synthesized AI answers**, which pull from GBP data, reviews, NAP consistency, and trusted third-party references.

**3A — Measurement**
- GEO-1: **AI-Search Visibility Score** — a SAIV-style metric capturing how often and how prominently a business appears across AI surfaces for tracked local prompts.
- GEO-2: Track across **Google AI Overviews, Google AI Mode, Gemini, ChatGPT, Perplexity, and Grok** (provider set configurable + extensible).
- GEO-3: **Geo-grid for AI** — because AI answers vary by location and by run, sample prompts across the coordinate grid and across repeated runs to produce a stable visibility picture, not a single snapshot.
- GEO-4: **Pseudo-rank / mention prominence** — capture order/position of the business within AI answers (first-mention vs. buried) as a proxy ranking.
- GEO-5: **Citation/source tracking** — identify which third-party sources and review platforms the AI references when answering about the business or category, so the agency knows where to invest.
- GEO-6: **Competitor AI-share** — same metrics for competitors; who dominates AI answers in each area.

**3B — Optimization (turn measurement into action)**
- GEO-7: **AI-readiness audit** — score the profile on the signals that feed AI answers: primary/secondary category specificity, Products/Services completeness, NAP consistency across the web (entity integrity), review recency/sentiment/coverage, photo recency and descriptive naming (Vision-AI signals), Q&A coverage, attributes, and post freshness.
- GEO-8: **Entity-consistency checker** — flag NAP and business-fact inconsistencies across directories that AI systems treat as verification failures.
- GEO-9: **GEO recommendation engine** — prioritized, profile-specific actions to increase AI citation likelihood (e.g., "add 3 missing services AI is asked about," "your competitor is cited for X; you lack the supporting signal").
- GEO-10: **Prompt library** — curated, niche-aware local prompts ("best [category] near me," "[category] open now in [area]," conversational long-tail) that the tracker monitors; agencies can add custom prompts.
- GEO-11: All GEO outputs feed reporting (Module 9) and the AI copilot (Module 8).

*Acceptance:* For a tracked location and prompt set, the platform returns an AI-Search Visibility Score, per-provider mention/prominence, the sources AI cited, a competitor comparison, and a ranked list of GEO actions — visualized on a grid.

> **Compliance note:** GEO measurement uses provider results responsibly and does not attempt to manipulate AI systems through deceptive means; recommendations focus on legitimate signal improvement (accuracy, completeness, genuine authority).

### Module 4 — Listings & Citation Management

- L-1: **NAP consistency scanner & citation audit** across major directories and niche sites.
- L-2: **Citation builder** (managed submissions + self-serve), with status tracking.
- L-3: **Multi-directory listing sync** — push consistent business data to a broad directory network (100+ platforms target via aggregators/partners).
- L-4: **Duplicate detection & suppression** workflow.
- L-5: Entity-consistency results shared with Module 3 (GEO depends on NAP integrity).

### Module 5 — Reputation & Reviews (compliance-critical)

- R-1: **Unified review inbox** — monitor and reply across all locations via the Reviews API. *(Constraint: API permits reply only — the platform cannot create, edit, or delete customer reviews or ratings. UI must never imply otherwise.)*
- R-2: **AI-assisted reply drafting** — tone-matched, on-brand drafts; human approval gate by default.
- R-3: **Compliant review-request campaigns** — requests are sent to **all** eligible customers equally. **Sentiment-based routing ("gating") is structurally impossible in the product** — there is no UI path to send review links only to predicted-happy customers, and no negative-feedback diversion branch.
- R-4: **AI sentiment & theme analysis** — convert review volume into themes and trends (e.g., "staff praised; parking criticized").
- R-5: **Review display widget** (schema-rich) for client websites.
- R-6: **Policy linting on replies/requests** — block/flag incentive language ("free," "discount," "coupon"), staff-name solicitation, and pressure tactics before they're sent (see §11).

*Acceptance:* When an operator attempts to compose a review-request flow, the product offers only equal-send campaigns; attempts to add an incentive phrase or sentiment filter are blocked with an explanation referencing the policy.

### Module 6 — Content, Posts & Media

- C-1: **GBP post scheduler** — standard/offer/event/recurring posts, content calendar, bulk CSV.
- C-2: **AI content generation** — posts and descriptions with length/keyword guidance (removes the "I don't know what to write" barrier).
- C-2a: **Local-context ingestion.** AI content generation injects hyper-local signals — nearby landmarks, cross-streets, neighborhood names, and locally-searched query phrasing — to maximize local relevance and AI-answer eligibility. Sourced from the location's geocoding + the GEO prompt library, and always passed through the pre-publish policy check. *(Adopted from LocateX; strengthens the GEO thesis since hyper-local entity signals feed AI Overviews.)*
- C-3: **Photo/video management** — bulk upload, descriptive auto-naming, geo-tagging, recency tracking (photos are an AI/Vision ranking signal).
- C-4: **Pre-publish policy + Vision-AI check** — screen images/text for policy compliance before publishing.
- C-5: **Q&A management** and **Products/Services management** — both feed relevance and AI answers.

### Module 7 — Profile Protection & Compliance (moat)

- P-1: **24/7 change monitoring** across 20+ critical fields (name, hours, categories, map pin, description, phone, URL, attributes), with near-real-time alerts.
- P-1a: **Protected baseline snapshot.** Each protected location stores an approved master snapshot (`profile_data_locked`) that all live-vs-baseline diffing compares against. *(Adopted from LocateX's locked-baseline idea — but see P-2a for how reverts are handled safely.)*
- P-2: **Suggested-edit alert + one-click reject/restore** workflow.
- P-2a: **Bounded revert policy (per location, configurable) — the safe version of "auto-revert."** Each location has a revert mode: `alert_only` (default), `auto_revert_critical` (only unambiguous high-risk changes such as a map-pin moved beyond a threshold, name change, or category change — rate-limited, fully audited, with an off switch), or `off`. The platform does **not** run unsupervised timer-based corrective writes against critical fields by default, because rapid automated critical-field edits are themselves a documented suspension trigger and can fight Google's own legitimate updates. Reverts are human-confirmed unless a narrow, clearly-malicious pattern is matched. *(Reframed from LocateX's silent 30-minute auto-revert lock to avoid creating the very suspension risk it aims to prevent.)*
- P-3: **Change history** correlated with rank/AI-visibility (attribute performance swings to specific edits).
- P-4: **Policy Compliance Engine** — validates every outbound action (reply, request, post, listing change) against current Google + FTC rules before execution.
- P-5: **Algorithm/Policy update tracker** — Super-Admin-curated feed of Google policy/algorithm changes that can auto-tighten guardrails platform-wide (directly satisfies the "protect against frequent Google updates" requirement).
- P-6: **Suspension-risk monitor + reinstatement assistant** — early-warning signals and a guided recovery workflow.
- P-7: **High-risk change queue (staggered critical-field updates).** Outbound edits to suspension-sensitive fields (name, primary category, phone) are not pushed in rapid batches. They pass through a managed queue that spaces and rate-limits them and re-checks them against the Policy Center before sending. This is legitimate change-management and transparency — *not* an attempt to disguise automated activity as organic. *(Adopted as the safe half of LocateX's "algorithmic sandbox"; the evasion framing is intentionally dropped.)*

### Module 8 — AI Automation Layer

- AI-1: **AI Copilot** — natural-language interface across the user's scope ("show my worst-performing locations for AI visibility and draft the fixes").
- AI-2: **Policy-bounded automation recipes** — auto-draft replies, auto-suggest posts, auto-alert — each with **two modes: Approval (human-in-the-loop, default) and Autopilot (bounded)**, configurable per client via the toggle engine.
- AI-3: **AI-narrated insights** — automatic plain-language commentary for dashboards and reports.
- AI-4: Every automation passes through the Policy Compliance Engine (P-4) before any external write.

### Module 9 — Reporting (named requirement)

- REP-1: **Customizable scheduled reports** — monthly, quarterly, yearly, and on-demand.
- REP-2: **White-label, multi-location rollups** — agency branding, PDF + live shareable link.
- REP-3: **Drag-and-drop report builder** — choose metrics (including GEO/AI-visibility), layout, cadence, recipients.
- REP-4: **AI-generated narrative summaries** per report.
- REP-5: Reports respect entitlements (omit toggled-off modules) and RBAC scope.

### Module 10 — Competitor Analysis (named requirement)

- CMP-1: **Competitor discovery & benchmarking** — reviews, posts, categories, photos, classic rank, and **AI-share**.
- CMP-2: **Geo-grid competitor overlay** — where competitors out-rank/out-cite you, block by block.
- CMP-3: **Distance-advantage & gap analysis** — surface winnable opportunities and missing signals.

### Module 11 — Extensibility & Integrations (named requirement: future flexibility)

- EXT-1: **Public REST API + webhooks**.
- EXT-2: **MCP server** exposing core tools to agentic AI clients.
- EXT-3: **Plugin/marketplace architecture** — new features ship as modules behind flags, no core changes.
- EXT-4: Roadmap hooks for **Apple Business Connect / Bing Places** (reduce single-channel dependence).
- EXT-5: CRM/BI export connectors (e.g., to data warehouses).

---

## 8. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Scale** | Support tenants with thousands of locations; geo-grid + AI scans are the heaviest workload — must scale horizontally via queues. |
| **Performance** | Dashboard P95 load < 2.5s; scan jobs async with progress; reports generate < 2 min for 100+ locations. |
| **Availability** | 99.9% target for the app tier; graceful degradation if a single provider API is down. |
| **Security** | Encryption in transit + at rest; OAuth tokens in a secrets vault; least-privilege; SOC 2 readiness as a roadmap goal; per-tenant data isolation. |
| **Privacy/Data** | Honor opt-outs (CAN-SPAM/TCPA on review requests); data residency options on roadmap; clear data-retention policy. |
| **Compliance** | Conform to Google Business Profile API policies and FTC review rules; see §11. |
| **Observability** | Full audit logging, job monitoring, API quota dashboards, alerting on provider failures/quota exhaustion. |
| **Cost control** | Credit metering on expensive operations (geo-grid, AI scans, LLM calls) surfaced to agencies. |

---

## 9. Compliance & Policy Framework (requirements #10 & #11) — **MANDATORY**

This framework is a product feature *and* an engineering constraint. It exists to satisfy "protect the client's GBP against frequent Google updates" and "use AI within Google policy."

### 9.1 Hard rules baked into the platform
1. **No review gating.** The product offers no mechanism to route review requests by predicted sentiment or to divert unhappy customers to private feedback instead of a public review.
2. **No incentivized reviews.** Reply/request composers block incentive language (free, discount, coupon, gift, raffle, loyalty points in exchange for reviews).
3. **No staff-name solicitation or on-premise pressure tactics** (kiosk/shared-tablet review flows are not provided).
4. **API write limits respected.** The platform never claims to create/edit/delete customer reviews or ratings — only reply, per the Reviews API.
5. **Project-ownership rule respected.** The platform does not let agencies/end-clients use one Business Profile project to avoid Google's requirement that programmatic users have their own project.
6. **Equal-send by design.** Review-request campaigns are structurally equal across eligible customers.

### 9.2 Adaptive guardrails (the "protect against frequent updates" mechanism)
- A Super-Admin **Policy Center** holds the current rule-set (Google policy + FTC rule) as configurable, versioned guardrails.
- When Google updates policy/algorithm, Super Admin updates the Policy Center; changes **propagate to every tenant's guardrails immediately**, tightening what automations may do — no client action required.
- The Policy Compliance Engine evaluates every external write against the active rule-set; violations are blocked with an explanation and logged.

### 9.3 FTC alignment
- Surface FTC Consumer Review Rule risks in-product; never facilitate fake/paid/suppressed reviews; respect customer opt-outs and messaging-frequency limits.

> Note: This framework reflects the policy landscape as of mid-2026 and is intentionally built to be **updated centrally** as rules evolve. It is product guidance, not legal advice; agencies remain responsible for their own compliance and should seek counsel where needed.

---

## 10. Analytics & Instrumentation
- Track activation funnel (connect → first scan → first report), per-feature adoption (esp. GEO), and entitlement usage to inform packaging.
- Instrument every blocked policy violation (proves the compliance value to buyers).
- Cohort retention by agency and by feature mix.

---

## 11. Assumptions, Dependencies, Constraints & Risks

**Assumptions**
- Agencies will pay a premium for consolidation + GEO + compliance.
- GBP APIs (Account Management, Business Information, Reviews v4, Local Posts, Performance) remain available with current capabilities.

**Dependencies**
- Google Business Profile API access approval (agency demo + policy review required).
- Third-party data: directory/citation network, AI-provider access for GEO tracking, geocoding/maps.

**Constraints**
- GBP API write limits (esp. reviews) cap automation scope by design.
- AI-provider results are non-deterministic → GEO needs repeated sampling for stable metrics (cost implication).
- Google API approval is not automatic and gates go-live.

**Key risks & mitigations**

| Risk | Impact | Mitigation |
|---|---|---|
| Google API policy change restricts capabilities | High | Adaptive Policy Center; abstraction layer over provider APIs; rapid-update process |
| AI-provider access/cost volatility for GEO | Med-High | Provider-agnostic GEO abstraction; credit metering; sampling controls |
| Google API access not approved in time | High | Early application; compliant demo build; phase GEO/read-only features that need less sensitive scopes first |
| Compliance misstep harms a client profile | High | Compliance-by-architecture; block-not-warn for hard rules; audit trail |
| Scope creep from "all-in-one" ambition | Med | Strict phasing (see roadmap); everything behind flags |

### 11.1 Known Limitations & Compliance Caveats (must be resolved before launch)

These are open issues the rest of the documents do **not** fully solve. They are surfaced here so they aren't mistaken for settled.

1. **Geo-grid / rank-scanning is a Terms-of-Service gray area.** Simulating searches from coordinate points and parsing Google results (the technique the whole market uses) can conflict with Google's Terms of Service, and the official Places API has its own restrictions on storing/displaying/ranking data. This sits in tension with the product's compliance-first posture. Decision needed: rely only on officially-permitted API data, use a licensed third-party rank-data provider, or accept and document the risk. Do not present geo-grid as "fully compliant" until this is settled.
2. **GEO/AI-provider querying has its own ToS and rate limits.** Programmatically querying ChatGPT, Gemini, Perplexity, Grok, etc. across a grid with repeated runs may violate each provider's terms, hit rate limits, and be costly. Prefer official APIs where available; document per-provider permissibility; meter aggressively.
3. **Google data retention/caching limits.** Storing `profile_data_live`, `profile_data_locked`, and long performance history may exceed what Google's API terms permit to cache. Confirm allowed retention windows and add a data-expiry/refresh policy rather than indefinite storage.
4. **`audit_log` immutability is not enforceable by schema alone.** "Append-only/immutable" requires DB-level enforcement (revoked UPDATE/DELETE grants, triggers, or write-once storage) — not just a convention. Implement enforcement explicitly.
5. **Reviews and review-requests contain personal data (PII).** Reviewer names/comments and customer contact data bring GDPR/CCPA obligations (lawful basis, retention limits, deletion/erasure requests, CAN-SPAM/TCPA on outreach). The schema has no PII-retention/erasure handling yet; add it before processing real customer data.
6. **"Compliant by architecture" is a strong claim — scope it to what's enforced.** It accurately describes the review-gating/incentive/reply-only/bounded-revert guarantees. It does **not** automatically cover items 1–3 above. Keep marketing claims aligned with what the Policy Engine actually enforces.

> These are product/engineering caveats, not legal advice. Resolve with qualified counsel and the relevant provider terms before go-live.

---

## 12. Out of Scope (v1)
Social media management beyond GBP; paid-ads management; website building; non-Google review platforms write-back beyond display; full data-residency regionalization (roadmap).

---

## 13. Open Questions
1. Initial directory/citation network partner(s) and AI-provider access path for GEO?
2. Billing model specifics: credit pricing for geo-grid vs. AI scans vs. LLM usage?
3. Which niches to seed the GEO prompt library with first?
4. White-label depth at launch (custom domain + email sending domain)?
5. SSO/SOC 2 timing relative to first enterprise agency deals?
