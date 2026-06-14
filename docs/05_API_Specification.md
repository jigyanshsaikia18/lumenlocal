# API Specification
## LumenLocal — REST API (v1)

| | |
|---|---|
| **Document type** | API Specification |
| **Version** | Draft v0.1 |
| **Base path** | `/api/v1` |
| **Auth** | Bearer JWT (session) or API key (for tenant integrations) |
| **Format** | JSON; `snake_case` fields; UTC ISO-8601 timestamps |
| **Companion docs** | `01_PRD.md`, `02_Technical_Architecture.md`, `04_Database_Schema.md` |

> This is the contract Claude Code implements in FastAPI. Every endpoint is **tenant-scoped** and **entitlement-gated**: the gateway resolves tenant/role first, then checks the feature flag, then runs the handler.

---

## 1. Conventions

- **Auth header:** `Authorization: Bearer <token>`.
- **Tenant context:** derived from the token; never passed by the client.
- **Pagination:** `?limit=50&cursor=<opaque>`; responses include `next_cursor`.
- **Errors:** `{ "error": { "code": "...", "message": "...", "details": {} } }`.
- **Standard codes:** `200/201` success, `400` validation, `401` unauthenticated, `403` `feature_disabled` or `forbidden`, `404` not found, `409` conflict, `422` policy violation (compliance block), `429` quota/rate limit.
- **Compliance block (422) example:**
  ```json
  { "error": { "code": "policy_violation", "message": "Review request blocked",
    "details": { "rule": "review_gating", "ruleset_version": 7 } } }
  ```

---

## 2. Auth & Identity

| Method | Path | Purpose | Min role |
|---|---|---|---|
| POST | `/auth/login` | Email/password or SSO exchange → JWT | public |
| POST | `/auth/refresh` | Refresh token | authenticated |
| POST | `/auth/logout` | Invalidate session | authenticated |
| GET | `/me` | Current user, roles, resolved scopes | authenticated |

---

## 3. Tenants, Clients, Users (admin)

| Method | Path | Purpose | Min role |
|---|---|---|---|
| GET/POST | `/tenants` | List/create tenants | super_admin |
| GET/PATCH | `/tenants/{id}` | Read/update tenant (white-label, plan, status) | super_admin / agency_admin (own) |
| GET/POST | `/clients` | List/create clients (sub-accounts) | agency_admin |
| GET/PATCH/DELETE | `/clients/{id}` | Manage a client | agency_admin |
| GET/POST | `/users` | List/invite users | agency_admin |
| PATCH | `/users/{id}/roles` | Assign role + scope | agency_admin |

---

## 4. Entitlements & Quotas (the toggle engine)

| Method | Path | Purpose | Min role |
|---|---|---|---|
| GET | `/features` | List registered feature flags + dependencies | agency_admin |
| GET | `/entitlements/resolve?client_id=&location_id=` | **Resolved** on/off set (4-level) | agency_admin |
| PUT | `/clients/{id}/features/{key}` | Set client-level override (`{ "state": true }`) | super_admin / agency_admin |
| PUT | `/locations/{id}/features/{key}` | Set location-level override | super_admin / agency_admin |
| GET | `/clients/{id}/preview?role=client_owner` | "What this client sees" preview | agency_admin |
| GET/PUT | `/quotas?scope_type=&scope_id=` | Read/set usage caps (api calls, scans, llm credits) | super_admin |
| GET | `/usage?scope_type=&scope_id=&period=` | Current consumption vs caps | agency_admin |

---

## 5. GBP Connection & Locations

| Method | Path | Purpose | Min role |
|---|---|---|---|
| POST | `/connections/oauth/start` | Begin client self-connect (returns Google consent URL) | account_manager |
| POST | `/connections/oauth/callback` | Handle OAuth redirect, vault token | system |
| POST | `/connections/proxy` | Agency-on-behalf connect flow | agency_admin |
| GET | `/connections/{id}/health` | Token status / expiry / scopes | account_manager |
| POST | `/locations/import` | Import locations from a connection (bulk) | account_manager |
| GET | `/locations` | List (filter by client) | analyst+ |
| GET/PATCH | `/locations/{id}` | Read/update location | account_manager |
| GET | `/locations/{id}/health-score` | Profile health/completeness grade | analyst+ |
| GET | `/locations/{id}/performance?from=&to=` | GBP metrics (calls, clicks, directions, views) | analyst+ |

---

## 6. Rank Tracking & GEO (flagship)

| Method | Path | Purpose | Min role |
|---|---|---|---|
| POST | `/locations/{id}/geogrid-scans` | Trigger classic geo-grid scan `{ search_term, grid_dimensions }` | account_manager |
| GET | `/locations/{id}/geogrid-scans` | History (SoLV trend) | analyst+ |
| GET | `/geogrid-scans/{scan_id}` | Single scan matrix | analyst+ |
| POST | `/locations/{id}/geo-ai-scans` | Trigger AI-search scan `{ provider[], prompt[], grid_dimensions, sample_runs }` | account_manager |
| GET | `/locations/{id}/geo-ai-scans` | AI-visibility history (SAIV trend) | analyst+ |
| GET | `/geo-ai-scans/{scan_id}` | Single AI scan (mentions, prominence, cited_sources) | analyst+ |
| GET/POST | `/geo-prompts?niche=` | List/add prompt library entries | account_manager |
| GET | `/locations/{id}/ai-readiness` | GEO audit + prioritized actions | analyst+ |

---

## 7. Reviews & Reputation (compliance-gated)

| Method | Path | Purpose | Min role |
|---|---|---|---|
| GET | `/locations/{id}/reviews` | List reviews (filter by rating/sentiment) | analyst+ |
| POST | `/reviews/{id}/reply` | **Reply only.** Passes Policy Engine; 422 on violation | account_manager |
| POST | `/reviews/{id}/reply/draft-ai` | AI-draft a reply (returns draft, not posted) | account_manager |
| GET | `/locations/{id}/review-sentiment` | Themes/sentiment summary | analyst+ |
| POST | `/clients/{id}/review-campaigns` | Create **equal-send** campaign (no sentiment routing) | account_manager |

> Note: there are **no** endpoints to create/edit/delete customer reviews (API forbids it), and **no** parameter anywhere to route requests by predicted sentiment (gating is structurally absent).

---

## 8. Content, Posts & Media

| Method | Path | Purpose | Min role |
|---|---|---|---|
| GET/POST | `/locations/{id}/posts` | List/create posts (status: draft/scheduled) | account_manager |
| POST | `/posts/{id}/generate-ai` | AI-generate content w/ local-context injection | account_manager |
| POST | `/posts/{id}/publish` | Publish (pre-publish policy + Vision check; 422 on block) | account_manager |
| POST | `/locations/{id}/media` | Upload photo/video (bulk) | account_manager |
| GET/POST | `/locations/{id}/qa` | Q&A management | account_manager |
| GET/POST | `/locations/{id}/services` | Products/Services management | account_manager |

---

## 9. Protection & Compliance

| Method | Path | Purpose | Min role |
|---|---|---|---|
| GET | `/locations/{id}/changes` | Profile change events (protection log) | analyst+ |
| POST | `/changes/{id}/revert` | One-click revert to baseline (bounded by revert_mode) | account_manager |
| PUT | `/locations/{id}/protection` | Set `is_protected`, `revert_mode` | agency_admin |
| GET | `/locations/{id}/suspension-risk` | Risk signals + reinstatement guidance | account_manager |
| GET | `/policy/rulesets` | List Policy Center versions | super_admin |
| PUT | `/policy/rulesets/active` | Publish new ruleset version (propagates platform-wide) | super_admin |
| GET | `/compliance/events?scope=` | Blocked/flagged violations (the proof trail) | agency_admin |

---

## 10. Competitors, Reporting & Automation

| Method | Path | Purpose | Min role |
|---|---|---|---|
| GET/POST | `/locations/{id}/competitors` | List/add competitors | account_manager |
| GET | `/locations/{id}/competitors/comparison` | Benchmark incl. AI-share | analyst+ |
| GET/POST | `/clients/{id}/reports` | List/build report configs | account_manager |
| POST | `/reports/{id}/generate` | Generate now (returns PDF ref) | account_manager |
| GET/POST | `/clients/{id}/report-schedules` | Monthly/quarterly/yearly schedules | account_manager |
| POST | `/copilot/ask` | Natural-language query within scope | analyst+ |
| GET/PUT | `/clients/{id}/automation` | Configure Approval vs Autopilot recipes | agency_admin |

---

## 11. System & Audit

| Method | Path | Purpose | Min role |
|---|---|---|---|
| GET | `/audit-log?scope=&from=&to=` | Immutable activity trail | agency_admin |
| GET | `/health` | Liveness/readiness | public |
| GET | `/webhooks` / POST | Manage outbound webhooks | agency_admin |

---

## 12. Cross-cutting middleware order (every request)
```
1. Authenticate (JWT/API key)        → 401 if invalid
2. Resolve tenant + role + scope     → 403 if out of scope
3. Resolve entitlement (4-level)     → 403 feature_disabled if off
4. Check quota (for metered ops)     → 429 if exceeded
5. (writes to Google) Policy Engine  → 422 if violation
6. Handler runs                      → audit-log on success
```
