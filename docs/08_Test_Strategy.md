# Test Strategy

| | |
|---|---|
| **Document type** | Test Strategy & Plan |
| **Version** | Draft v0.1 |
| **Companion docs** | `01_PRD.md`, `05_API_Specification.md`, `06_Backlog_Epics_and_Stories.md` |

> Philosophy: tests are written **with** each ticket, not after the phase. The compliance and entitlement logic are the highest-risk areas and get the most coverage. "Done" = tests pass.

---

## 1. The testing pyramid for this project

| Layer | Tooling | What it covers | Where |
|---|---|---|---|
| **Unit** (most) | `pytest` (backend), `vitest` (frontend) | Pure logic: entitlement resolver, geo-grid math, policy rules, SAIV calc, RBAC checks | per module |
| **Integration** | `pytest` + test DB (Postgres in Docker), HTTP client | Endpoint behavior, DB constraints, middleware order, tenant isolation | `backend/tests/integration` |
| **Contract** | schema assertions against `05_API_Specification.md` | Status codes, error shapes (403/422/429), payload fields | per endpoint |
| **Component (UI)** | `vitest` + React Testing Library | Widgets render, feature-off hides UI, role gating | `frontend/src/**/__tests__` |
| **E2E** (few) | `Playwright` | Critical journeys: connect GBP → scan → report; review reply blocked on violation | `e2e/` |

---

## 2. Highest-priority test suites (write these carefully)

### 2.1 Entitlement resolver (the differentiator)
- Resolves correctly at all 4 levels with **location > client > plan > default** precedence.
- Disabled feature → API returns `403 feature_disabled`.
- Dependency rule: enabling a dependent feature without its prerequisite is rejected.
- Toggling reflects in the "what this client sees" preview.

### 2.2 Compliance engine (the moat) — test the *blocks*
- Review reply with incentive language ("discount") → **422 policy_violation**, `rule=incentive_language`.
- Staff-name solicitation in a request → blocked.
- **Assert structural absence:** there is no API field or campaign mode that routes by sentiment (a test that greps the codebase/schema for a gating field and fails if found).
- No endpoint exists to create/delete a customer review (contract test asserts 404/405).
- Publishing a new Policy Center version propagates: a previously-allowed action becomes blocked.
- Every external-write path calls the engine (test a representative endpoint per write type).

### 2.3 Profile protection (bounded, not silent)
- Change detection flags a critical-field diff and emits an alert.
- `revert_mode = alert_only` (default) does **not** auto-write to Google.
- `revert_mode = auto_revert_critical` only reverts the allowed narrow patterns, is rate-limited, and is audited.

### 2.4 Tenant isolation (security)
- A user from Tenant A cannot read/write any Tenant B resource (parametrized across endpoints).
- RBAC: each role can do only its capabilities; out-of-scope → 403.

### 2.5 Geo-grid + GEO math
- Coordinate generation for given center/radius/dimensions is correct (golden values).
- SoLV and SAIV computed correctly from fixture scan results.
- GEO provider abstraction normalizes a mocked provider response into mention/prominence/citation records.

---

## 3. Test data & fixtures
- Use factory fixtures (e.g. `factory_boy`) for tenants/clients/locations/users.
- **Mock all external providers** (Google APIs, AI-search providers, LLM, directories) — never hit real APIs in unit/integration tests. Record/replay fixtures for provider responses.
- A seeded "demo tenant" with one client and one location for E2E.

---

## 4. What to run, and when
- **Per ticket (local):** `pytest <touched module>` + `vitest <touched component>`.
- **Before commit:** full backend `pytest` + frontend `vitest`, lint/format.
- **In CI (every push):** lint → unit → integration (spins up Postgres+Redis) → contract; E2E on PRs to main.
- **Coverage targets:** ≥85% on compliance engine and entitlement resolver; ≥70% overall to start.

---

## 5. Manual / exploratory checks (per phase exit)
- Walk the phase's "exit criteria" from `03_Phased_Roadmap.md` by hand.
- Verify a toggled-off feature truly disappears (UI + API + report).
- Try to make a policy violation through the UI and confirm it's blocked with a clear message.

---

## 6. Prompts to give Claude Code for testing (see guidebook §6)
- "Write pytest unit tests for the entitlement resolver covering all four precedence levels and the dependency rule. Mock the DB layer. Show me the tests before implementing."
- "Add an integration test proving a review reply containing the word 'discount' returns 422 with rule=incentive_language."
- "Write a test that fails if any schema column or API field could enable sentiment-based review routing."
- "Run the backend test suite and fix only the failing tests related to this ticket — don't touch unrelated tests."
