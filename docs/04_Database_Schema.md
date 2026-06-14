# Database Schema Design
## LumenLocal — Agency-First, GEO-Native GBP Platform

| | |
|---|---|
| **Document type** | Relational Database Schema (PostgreSQL 15+) |
| **Version** | Draft v0.1 |
| **Status** | For review |
| **Companion docs** | `01_PRD.md`, `02_Technical_Architecture.md`, `03_Phased_Roadmap.md` |

> Extends the LocateX baseline schema (`tenants`, `users`, `locations`, `geogrid_scans`) and adds the tables the architecture requires: granular entitlements + quotas, RBAC, GEO/AI-search, protection/compliance, reviews, posts, reporting, and audit. Engine: **PostgreSQL 15+**, using `JSONB` for flexible fields and `gen_random_uuid()` for keys. Conventions: every tenant-scoped table carries `tenant_id` for isolation; timestamps default to `CURRENT_TIMESTAMP`; foreign keys are indexed.

---

## 1. Schema Overview (entity map)

```
tenants ──┬── users ── user_roles ── role_permissions
          ├── plans ── plan_features
          ├── clients ──┬── locations ──┬── gbp_connections (OAuth, vaulted)
          │             │               ├── geogrid_scans
          │             │               ├── geo_ai_scans (AI-search visibility)
          │             │               ├── profile_change_events (protection)
          │             │               ├── reviews ── review_replies
          │             │               ├── review_campaigns
          │             │               ├── posts
          │             │               └── competitors
          │             └── client_features / location_features (entitlement overrides)
          ├── usage_quotas + usage_counters (Super-Admin caps)
          ├── policy_rulesets (Policy Center, versioned)
          ├── compliance_events (blocked violations)
          ├── reports + report_schedules
          └── audit_log (immutable)
```

---

## 2. Core Tenancy & Identity

### `tenants` — agency / enterprise accounts *(extends LocateX)*
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK, default `gen_random_uuid()` | Tenant identifier |
| company_name | VARCHAR(255) | NOT NULL | Agency / brand name |
| plan_id | UUID | FK → plans(id) | Subscription tier |
| white_label | JSONB | NOT NULL default '{}' | Logo, colors, custom domain, sending domain |
| status | VARCHAR(20) | NOT NULL default 'active' | active / suspended / trial |
| created_at | TIMESTAMP | default now | |

### `clients` — sub-accounts (the agency's customers)
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | Client identifier |
| tenant_id | UUID | FK → tenants(id), INDEX | Parent agency |
| name | VARCHAR(255) | NOT NULL | Client business name |
| niche | VARCHAR(120) | | Seeds GEO prompt library |
| status | VARCHAR(20) | default 'active' | |
| created_at | TIMESTAMP | default now | |

### `users` — platform users *(extends LocateX)*
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | User identifier |
| tenant_id | UUID | FK → tenants(id), INDEX | Parent tenant |
| email | VARCHAR(255) | UNIQUE, INDEX, NOT NULL | Login credential |
| password_hash | VARCHAR(255) | NULL (NULL when SSO) | bcrypt hash |
| sso_subject | VARCHAR(255) | NULL, INDEX | SAML/OIDC subject |
| status | VARCHAR(20) | default 'active' | |
| two_fa_enabled | BOOLEAN | default false | |
| created_at | TIMESTAMP | default now | |

### `user_roles` — RBAC assignment (supports scope + custom roles)
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | |
| user_id | UUID | FK → users(id), INDEX | |
| role | VARCHAR(50) | NOT NULL | super_admin / agency_admin / account_manager / client_owner / analyst / custom |
| scope_type | VARCHAR(20) | NOT NULL | tenant / client / location |
| scope_id | UUID | INDEX | The client/location the role applies to (NULL = whole tenant) |

### `role_permissions` — capability map (for custom roles)
| Column | Type | Constraints | Description |
|---|---|---|---|
| role | VARCHAR(50) | PK part | Role key |
| permission | VARCHAR(80) | PK part | e.g. `reviews.reply`, `protection.reject_edit`, `reports.schedule` |

---

## 3. Plans, Entitlements & Quotas (the toggle engine + Super-Admin caps)

### `plans`
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | |
| name | VARCHAR(120) | NOT NULL | Tier name |
| price_meta | JSONB | default '{}' | Seat/location/credit pricing |

### `features` — registry of toggleable capabilities
| Column | Type | Constraints | Description |
|---|---|---|---|
| key | VARCHAR(80) | PK | e.g. `geogrid`, `geo_ai`, `ai_writer`, `review_automation`, `protection` |
| name | VARCHAR(120) | NOT NULL | Display name |
| dependencies | JSONB | default '[]' | Prerequisite feature keys |
| default_state | BOOLEAN | default false | |

### `plan_features` / `client_features` / `location_features` — 4-level resolution
*(most specific wins: location > client > plan > default)*
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | |
| scope_id | UUID | INDEX | plan_id / client_id / location_id depending on table |
| feature_key | VARCHAR(80) | FK → features(key) | |
| state | BOOLEAN | NOT NULL | on/off override at this level |
| set_by | UUID | FK → users(id) | Who changed it |
| set_at | TIMESTAMP | default now | |

> LocateX stored toggles as a single `feature_gates` JSONB on the tenant. We keep a denormalized `feature_gates` cache for fast reads, but the **source of truth is the resolved set across these tables** so we get per-client and per-location granularity, dependency enforcement, and an audit trail.

### `usage_quotas` — Super-Admin hard caps *(adopted from LocateX, generalized)*
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | |
| scope_type | VARCHAR(20) | NOT NULL | tenant / client |
| scope_id | UUID | INDEX | |
| metric | VARCHAR(40) | NOT NULL | `google_api_calls` / `geogrid_scans` / `ai_scans` / `llm_credits` |
| period | VARCHAR(20) | default 'monthly' | |
| limit_value | BIGINT | NOT NULL | Hard cap |
| on_exceed | VARCHAR(20) | default 'pause' | pause / alert / block |

### `usage_counters` — consumption tracking
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | |
| scope_type | VARCHAR(20) | | tenant / client |
| scope_id | UUID | INDEX | |
| metric | VARCHAR(40) | INDEX | matches usage_quotas.metric |
| period_start | DATE | INDEX | |
| used_value | BIGINT | default 0 | Incremented by workers |

---

## 4. GBP Connection & Locations

### `gbp_connections` — OAuth bindings (dual-route)
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | |
| client_id | UUID | FK → clients(id), INDEX | |
| connect_method | VARCHAR(20) | NOT NULL | self_serve / agency_proxy |
| token_ref | VARCHAR(255) | NOT NULL | Reference to vaulted token (never store raw token in DB) |
| scopes | JSONB | default '[]' | Granted scopes |
| token_status | VARCHAR(20) | default 'healthy' | healthy / expiring / disconnected |
| expires_at | TIMESTAMP | INDEX | Drives re-auth alerts |

> Raw OAuth tokens live in the **secrets vault**, not Postgres. `token_ref` points to them.

### `locations` — physical outlets *(extends LocateX)*
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | |
| tenant_id | UUID | FK → tenants(id), INDEX | |
| client_id | UUID | FK → clients(id), INDEX | |
| google_place_id | VARCHAR(255) | INDEX | Google Maps ID |
| latitude | NUMERIC(9,6) | | For geo-grid centroid + local-context |
| longitude | NUMERIC(9,6) | | |
| profile_data_live | JSONB | NOT NULL | Live business details from GBP API |
| profile_data_locked | JSONB | | Approved baseline for diffing (protection) |
| is_protected | BOOLEAN | default true | Protection on/off |
| revert_mode | VARCHAR(20) | default 'alert_only' | alert_only / auto_revert_critical / off — **bounded, configurable; not silent timer-writes** |
| created_at | TIMESTAMP | default now | |

---

## 5. Rank Tracking & GEO (the differentiator)

### `geogrid_scans` — classic spatial rankings *(from LocateX)*
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | |
| location_id | UUID | FK → locations(id), INDEX | |
| search_term | VARCHAR(255) | NOT NULL | Target keyword |
| grid_dimensions | INTEGER | NOT NULL | 3,5,7,9,10 |
| matrix_results | JSONB | NOT NULL | Coord → rank + competitors |
| solv | NUMERIC(5,2) | | Share of Local Voice |
| run_at | TIMESTAMP | default now, INDEX | |

### `geo_ai_scans` — AI-search visibility *(new — flagship)*
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | |
| location_id | UUID | FK → locations(id), INDEX | |
| provider | VARCHAR(40) | NOT NULL | ai_overviews / ai_mode / gemini / chatgpt / perplexity / grok |
| prompt | VARCHAR(500) | NOT NULL | Local prompt sampled |
| grid_dimensions | INTEGER | | Geo-grid-for-AI sampling |
| sample_runs | INTEGER | default 1 | Repeats for stability |
| matrix_results | JSONB | NOT NULL | Coord → mention/prominence per run |
| saiv | NUMERIC(5,2) | | AI-Search Visibility score |
| cited_sources | JSONB | default '[]' | Sources the AI referenced |
| run_at | TIMESTAMP | default now, INDEX | |

### `geo_prompts` — niche-aware prompt library
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | |
| niche | VARCHAR(120) | INDEX | NULL = global |
| prompt | VARCHAR(500) | NOT NULL | |
| is_custom | BOOLEAN | default false | Agency-added |
| tenant_id | UUID | NULL | Set when custom |

### `competitors`
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | |
| location_id | UUID | FK → locations(id), INDEX | |
| google_place_id | VARCHAR(255) | INDEX | |
| name | VARCHAR(255) | | |
| metrics | JSONB | default '{}' | reviews, posts, classic rank, ai_share |

---

## 6. Reviews, Posts & Reporting

### `reviews` (read/aggregate; API is reply-only)
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | |
| location_id | UUID | FK → locations(id), INDEX | |
| google_review_id | VARCHAR(255) | UNIQUE | |
| rating | SMALLINT | | 1–5 |
| comment | TEXT | | |
| sentiment | VARCHAR(20) | | AI-derived |
| created_at | TIMESTAMP | INDEX | |

### `review_replies`
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | |
| review_id | UUID | FK → reviews(id) | |
| body | TEXT | NOT NULL | |
| status | VARCHAR(20) | default 'draft' | draft / pending_approval / published |
| compliance_checked | BOOLEAN | default false | Passed Policy Engine |
| authored_by | VARCHAR(20) | | human / ai |

### `review_campaigns` (equal-send by design; **no sentiment routing column exists**)
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | |
| client_id | UUID | FK → clients(id) | |
| send_mode | VARCHAR(20) | NOT NULL default 'equal_all' | Only value allowed — gating is structurally impossible |
| channel | VARCHAR(20) | | email / sms |
| created_at | TIMESTAMP | default now | |

### `posts`
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | |
| location_id | UUID | FK → locations(id), INDEX | |
| type | VARCHAR(20) | | standard / offer / event / recurring |
| content | JSONB | NOT NULL | Body, media refs, local-context tokens |
| scheduled_at | TIMESTAMP | INDEX | |
| status | VARCHAR(20) | default 'draft' | draft / scheduled / published / blocked |
| policy_checked | BOOLEAN | default false | Passed pre-publish check |

### `reports` / `report_schedules`
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | |
| client_id | UUID | FK → clients(id), INDEX | |
| config | JSONB | NOT NULL | Builder layout, metrics (incl. GEO), branding |
| interval | VARCHAR(20) | | monthly / quarterly / yearly / on_demand |
| last_generated_at | TIMESTAMP | | |
| output_ref | VARCHAR(255) | | Object-store ref to PDF |

---

## 7. Compliance, Protection & Audit

### `policy_rulesets` — Policy Center (versioned; the "protect against updates" mechanism)
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | |
| version | INTEGER | NOT NULL, INDEX | Increments on each Google/FTC update |
| rules | JSONB | NOT NULL | Machine-evaluable guardrails |
| effective_from | TIMESTAMP | default now | Propagates platform-wide |
| is_active | BOOLEAN | default true | |

### `compliance_events` — blocked violations (the audit trail that sells the value)
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | |
| tenant_id | UUID | INDEX | |
| action_type | VARCHAR(30) | | review_reply / review_request / post / listing_edit |
| outcome | VARCHAR(20) | | blocked / flagged / passed |
| rule_violated | VARCHAR(120) | | e.g. incentive_language, gating, staff_name |
| ruleset_version | INTEGER | | Which Policy Center version applied |
| created_at | TIMESTAMP | default now, INDEX | |

### `profile_change_events` — protection monitoring
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | |
| location_id | UUID | FK → locations(id), INDEX | |
| field | VARCHAR(60) | | Which of the 20+ monitored fields |
| old_value | JSONB | | From baseline |
| new_value | JSONB | | Detected live value |
| severity | VARCHAR(20) | | low / medium / high (e.g. map-pin move = high) |
| action_taken | VARCHAR(20) | | alerted / reverted / ignored |
| detected_at | TIMESTAMP | default now, INDEX | |

### `audit_log` — immutable, platform-wide
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | |
| tenant_id | UUID | INDEX | |
| actor_user_id | UUID | | Who |
| action | VARCHAR(80) | | What capability |
| target_type | VARCHAR(40) | | Entity type |
| target_id | UUID | | Entity id |
| before | JSONB | | State before |
| after | JSONB | | State after |
| created_at | TIMESTAMP | default now, INDEX | Append-only |

---

## 8. Indexing & Isolation Notes
- Every tenant-scoped query filters on `tenant_id`; consider row-level security (RLS) policies in Postgres to enforce isolation at the database layer.
- Heavy time-series tables (`geogrid_scans`, `geo_ai_scans`, `profile_change_events`) are partitioned by month and indexed on (`location_id`, `run_at`/`detected_at`) for fast trend queries.
- `usage_counters` is incremented transactionally by workers; quota checks read the current period row before enqueuing expensive jobs.
- Tokens are never stored raw in Postgres — only `token_ref` to the vault.

---

## 9. What changed vs. the LocateX baseline (summary)
- **Kept & extended:** `tenants`, `users`, `locations` (added `client_id`, lat/long, `revert_mode`), `geogrid_scans` (added `solv`).
- **Generalized:** tenant-level `feature_gates` JSONB → full 4-level entitlement tables + cache; API quotas → `usage_quotas`/`usage_counters`.
- **Added for differentiation:** `geo_ai_scans`, `geo_prompts`, `competitors`.
- **Added for compliance/protection:** `policy_rulesets`, `compliance_events`, `profile_change_events`, `audit_log`, and a **bounded** `revert_mode` instead of silent auto-revert.
- **Added for operations:** `clients`, `plans`, `gbp_connections`, RBAC tables, reviews/posts/reports tables.
