---
name: new-endpoint
description: Standard recipe for adding a FastAPI v1 endpoint to LumenLocal — Pydantic schema, route under app/api/v1, the tenant→RBAC→entitlement→quota→policy middleware chain (05_API_Specification.md §12), and a pytest contract test. Use when adding or scaffolding a new API endpoint.
---

# Adding a FastAPI endpoint

Follow these four steps in order. Every endpoint is tenant-scoped and entitlement-gated — no exceptions. Match paths and status codes to `/docs/05_API_Specification.md`; match columns to `/docs/04_Database_Schema.md` (don't invent either).

## 1. Define the Pydantic schema

In `backend/app/schemas/<resource>.py`. Separate request and response models; `snake_case` fields, UTC ISO-8601 datetimes.

```python
class GeogridScanCreate(BaseModel):
    search_term: str
    grid_dimensions: Literal["5x5", "7x7", "9x9"]

class GeogridScanOut(BaseModel):
    id: UUID
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

Never accept `tenant_id`/`client_id` as a body field for scoping — it comes from the token (§1).

## 2. Add the route under `backend/app/api/v1`

One router per resource (`backend/app/api/v1/<resource>.py`), registered on the v1 app. Keep the handler thin — validation in the schema, business logic in a service.

```python
@router.post("/locations/{location_id}/geogrid-scans",
             response_model=GeogridScanOut, status_code=201)
async def create_geogrid_scan(
    location_id: UUID,
    body: GeogridScanCreate,
    ctx: RequestContext = Depends(require_endpoint(
        min_role="account_manager",
        feature="geogrid_scan",
        quota="scans",
    )),
):
    return await scan_service.enqueue(ctx, location_id, body)
```

## 3. Enforce the middleware chain — order from §12

Run as dependencies, in this exact order. The `require_endpoint(...)` dependency composes them; do not reorder or skip a layer.

| # | Layer | Failure |
|---|-------|---------|
| 1 | Authenticate (JWT / API key) | `401` |
| 2 | Resolve tenant + role + scope (RBAC) | `403 forbidden` |
| 3 | Resolve entitlement (4-level) | `403 feature_disabled` |
| 4 | Check quota (metered ops only) | `429` |
| 5 | Policy Engine — **only on writes to Google** | `422 policy_violation` |
| 6 | Handler runs → write `audit_log` on success | — |

Steps 1–4 apply to every endpoint. Step 5 applies only to handlers that write to Google (reviews, posts, profile edits) — it is mandatory there and no module may bypass it. Read endpoints skip 4 and 5.

## 4. Write a pytest contract test

In `backend/tests/api/v1/test_<resource>.py`. A contract test asserts the §12 chain and the documented status codes — not just the happy path. Minimum cases:

```python
def test_happy_path_201(client, account_manager_token): ...      # 201 + response schema
def test_unauthenticated_401(client): ...                        # no token
def test_out_of_scope_403(client, other_tenant_token): ...       # RBAC
def test_feature_disabled_403(client, token_no_entitlement): ... # entitlement off
def test_quota_exceeded_429(client, token_at_quota_cap): ...     # metered ops
# writes-to-Google handlers only:
def test_policy_violation_422(client, token, blocking_payload): ...
```

Assert the error body shape: `{"error": {"code", "message", "details"}}` (§1). Run `pytest` before calling the ticket done.

## Compliance reminders
- Reviews are reply-only; campaigns are `equal_all` — never add sentiment-routing fields.
- Every external write to Google passes the Policy Engine (step 5) first.
- Tenant-scope every DB query; `audit_log` is immutable at the DB level.
