---
name: new-endpoint
description: Standard recipe for adding a FastAPI v1 endpoint to LumenLocal — Pydantic schema, route under app/api/v1, the tenant→RBAC→entitlement→quota→policy middleware chain (05_API_Specification.md §12), and a pytest contract test. Use when adding or scaffolding a new API endpoint.
---

# Adding a FastAPI endpoint
Four steps, in order. Every endpoint is tenant-scoped and entitlement-gated. Match paths/status codes to `/docs/05_API_Specification.md`; match columns to `/docs/04_Database_Schema.md` (invent neither).

## 1. Pydantic schema — `backend/app/schemas/<resource>.py`
Separate request/response models; `snake_case`, UTC ISO-8601 datetimes, `ConfigDict(from_attributes=True)` on outputs. Never accept `tenant_id`/`client_id` in the body — scoping comes from the token.
## 2. Route — `backend/app/api/v1/<resource>.py`
One thin router per resource (logic in a service), on the v1 app. Compose the chain via one dependency:
```python
@router.post("/locations/{location_id}/geogrid-scans", response_model=GeogridScanOut, status_code=201)
async def create_geogrid_scan(location_id: UUID, body: GeogridScanCreate,
    ctx: RequestContext = Depends(require_endpoint(min_role="account_manager", feature="geogrid_scan", quota="scans"))):
    return await scan_service.enqueue(ctx, location_id, body)
```
## 3. Middleware order (§12) — do not reorder or skip
| # | Layer | Failure |
|---|-------|---------|
| 1 | Authenticate (JWT / API key) | `401` |
| 2 | Resolve tenant + role + scope | `403 forbidden` |
| 3 | Resolve entitlement (4-level) | `403 feature_disabled` |
| 4 | Check quota (metered ops only) | `429` |
| 5 | Policy Engine — **writes to Google only** | `422 policy_violation` |
| 6 | Handler → write `audit_log` on success | — |

Steps 1–3 always apply; read endpoints skip 4–5; step 5 is mandatory on any Google write — no bypass.
## 4. Contract test — `backend/tests/api/v1/test_<resource>.py`
Assert the chain, not just the happy path. Error body `{"error":{"code","message","details"}}`. Run `pytest` before done.
```python
def test_happy_path_201(client, account_manager_token): ...
def test_unauthenticated_401(client): ...
def test_out_of_scope_403(client, other_tenant_token): ...
def test_feature_disabled_403(client, token_no_entitlement): ...
def test_quota_exceeded_429(client, token_at_quota_cap): ...
def test_policy_violation_422(client, token, blocking_payload): ...  # Google writes only
```
