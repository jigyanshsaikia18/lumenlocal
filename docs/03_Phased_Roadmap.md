# Phased Delivery Roadmap
## LumenLocal — Agency-First, GEO-Native GBP Platform

| | |
|---|---|
| **Document type** | Phased Roadmap |
| **Version** | Draft v0.1 |
| **Status** | For review |
| **Companion docs** | `01_PRD.md`, `02_Technical_Architecture.md`, `04_Database_Schema.md` |

> Durations are **relative effort guidance**, not commitments — calibrate to team size. The sequence matters more than the calendar. The guiding rule: **build the agency spine and compliance gateway first, prove the GEO differentiator early, then broaden.**

---

## Sequencing Logic

1. **Platform spine before features.** RBAC, multi-tenancy, the entitlement engine, GBP connection, and the compliance gateway are prerequisites for everything and cannot be retrofitted cleanly.
2. **Differentiator early, not last.** GEO is the reason to choose this product — it appears in the MVP, not v2, so early design partners feel the difference.
3. **Compliance from day one.** The Policy Compliance Engine ships with the first external-write feature (reviews), because a compliance bolt-on defeats the "compliance-by-architecture" promise.
4. **Google API approval is on the critical path.** Begin the application in Phase 0; gate sensitive-scope features behind it.
5. **Everything behind a flag** so each phase can dark-launch to design-partner agencies.

---

## Phase 0 — Foundations & Approvals *(pre-build, short)*

**Goal:** De-risk the dependencies that can block everything else.

- Apply for **Google Business Profile API access**; prepare a compliant demo build (approval is not automatic and is on the critical path).
- Secure **AI-search provider access** path for GEO and an **LLM provider**.
- Select **citation/directory network** partner and geocoding/maps provider.
- Lock core **ADRs** (stack, data stores, queue) and the tenancy/isolation model.
- Define the **capability/permission catalog** and the **feature-flag key registry** (so everything ships flag-gated from commit #1).

**Exit criteria:** API application submitted; provider paths confirmed; ADRs signed; flag registry + permission catalog drafted.

---

## Phase 1 — Agency Spine (MVP Part 1)

**Goal:** A multi-tenant, white-label shell an agency can log into, with clients/locations connected.

**Build:**
- Multi-tenancy + **Tenant→Client→Location registry**.
- **Identity & RBAC** (core roles + custom-role scaffold; 2FA).
- **Entitlement / Feature-Flag Engine** with 4-level resolution + "What this client sees" preview + audit log. *(Named requirement — ships in MVP.)*
- **GBP connection flows**: client self-connect (OAuth) **and** agency-on-behalf connect, respecting Google's project-ownership rule.
- **White-label theming** (logo, colors; custom domain can follow).
- **Premium Dashboard v1**: Profile Health Score + GBP Performance metrics + multi-location view.
- **Audit & activity log**; **billing/metering scaffold** (credits defined, not yet monetized).

**Exit criteria:** An agency can onboard, connect a client's locations both ways, toggle features per client, and see a branded dashboard with real performance metrics.

---

## Phase 2 — GEO Differentiator + Classic Rank (MVP Part 2)

**Goal:** Deliver the headline value — measurable, improvable AI-search visibility — alongside classic tracking.

**Build:**
- **Classic rank tracking**: geo-grid (SoLV) + keyword tracker (map/organic, mobile/desktop), scheduled scans, credit metering.
- **GEO / AI-Search Visibility (flagship):**
  - AI-Search Visibility Score (SAIV-style) across AI Overviews, AI Mode, Gemini, ChatGPT, Perplexity, Grok via the provider abstraction.
  - Geo-grid-for-AI sampling (multi-location, repeated runs for stability).
  - Mention prominence + **citation/source tracking** (which sources AI references).
  - **AI-readiness audit** + **entity-consistency checker** (NAP integrity).
  - **GEO recommendation engine** + niche-aware **prompt library**.
- **Async/queue layer** hardened for scan + sampling fan-out.

**Exit criteria:** For a tracked location, the platform returns classic rank + an AI-visibility score, the sources AI cited, and a prioritized GEO action list — visualized on a grid. **This is the minimum lovable, sellable product.**

> ✅ **MVP = Phase 1 + Phase 2.** Ship to design-partner agencies here.

---

## Phase 3 — Reputation, Content & the Compliance Gateway

**Goal:** Add the highest-frequency daily-use features — with compliance built in from the first external write.

**Build:**
- **Policy Compliance Engine + Policy Center** (versioned rule-set) — ships *with* the first write feature.
- **Reviews & Reputation**: unified inbox (reply-only via Reviews v4), AI-assisted reply drafting (approval mode), **compliant equal-send review campaigns** (gating structurally impossible), reply/request **policy linting**, sentiment/theme analysis, review widget.
- **Content & Posts**: scheduler (standard/offer/event/recurring), AI content generation, photo/video management with descriptive naming, pre-publish Vision-AI/policy check, Q&A + Products/Services management.

**Exit criteria:** Operators run daily review and posting workflows; every external write passes the compliance gateway; attempts at gating/incentives/staff-name solicitation are blocked with explanations.

---

## Phase 4 — Protection, Competitors & Reporting

**Goal:** Lock in retention via the moat (protection) and the #1 agency retention tool (reporting).

**Build:**
- **Profile Protection**: 24/7 change monitoring (20+ fields), suggested-edit alerts + one-click reject/restore, change-to-rank correlation, suspension-risk monitor + reinstatement assistant.
- **Algorithm/Policy update tracker** wired into the Policy Center (the "protect against frequent Google updates" mechanism, operationalized).
- **Competitor Analysis**: discovery/benchmarking incl. **AI-share**, geo-grid competitor overlay, distance-advantage/gap analysis.
- **Reporting**: drag-and-drop builder, customizable **monthly/quarterly/yearly** scheduled reports, white-label multi-location rollups (PDF + live link), **AI-narrated summaries**, entitlement- and RBAC-aware.

**Exit criteria:** Agencies get near-real-time protection alerts, competitor benchmarks (classic + AI), and one-click branded reports across 100+ locations.

---

## Phase 5 — AI Automation, Listings Scale & Extensibility

**Goal:** Maximize automation (within policy) and open the platform up.

**Build:**
- **AI Copilot** (natural-language across scope) + **policy-bounded automation recipes** with **Approval / Autopilot** modes, toggled per client.
- **Listings & Citations at scale**: NAP scanner, citation builder, multi-directory sync (100+ via aggregators), duplicate detection/suppression.
- **Extensibility**: public REST API + webhooks, **MCP server**, **module/marketplace architecture**, CRM/BI export.

**Exit criteria:** Repetitive work runs on bounded autopilot with audit trails; third-party/internal modules can be added behind flags; external systems integrate via API/MCP.

---

## Phase 6 — Enterprise Hardening & Channel Expansion *(ongoing)*

**Goal:** Move upmarket and reduce single-channel dependence.

**Build (prioritize by deal demand):**
- SSO depth, **SOC 2**, data-residency options, advanced quota/cost governance.
- **Apple Business Connect / Bing Places** tracking + management.
- Advanced billing/packaging experiments informed by entitlement-usage analytics.
- Deeper white-label (sending domains, fully custom client portals).

**Exit criteria:** Platform supports enterprise agency procurement and multi-channel local presence beyond Google.

---

## Roadmap at a Glance

| Phase | Theme | Headline outcome | Named PRD requirements landed |
|---|---|---|---|
| 0 | Foundations & approvals | Dependencies de-risked | API approval path, flag registry |
| 1 | Agency spine | Branded multi-tenant shell + dual connect + **toggle engine** | RBAC (#4), toggle engine (#5), connect flows (#6), dashboard (#7,#13) |
| 2 | **GEO + classic rank** | **Measurable AI-search visibility (MVP)** | Differentiator; rank tracking |
| 3 | Reputation, content, **compliance gateway** | Daily workflows, compliant by design | Compliance (#10,#11), AI use (#11) |
| 4 | Protection, competitors, reporting | Moat + retention | Reports (#8), competitors (#12), protection (#10) |
| 5 | AI automation, listings, extensibility | Bounded autopilot + open platform | AI automation (#11), flexibility (#14) |
| 6 | Enterprise + channels | Upmarket + multi-channel | Future-proofing (#14, #15) |

---

## Phasing Guardrails (how to avoid the "all-in-one" trap)
- **Don't move a phase forward without its exit criteria met.** Breadth is the biggest risk to this product.
- **Keep the compliance gateway ahead of every write feature** — never let a write ship "compliance later."
- **Validate GEO with design partners at end of Phase 2** before investing in Phases 3–5 breadth.
- **Use the flag engine to dark-launch** every phase to a small agency cohort first.
- **Re-confirm Google API scope/policy at the start of each phase** and adjust via the Policy Center, not code.
