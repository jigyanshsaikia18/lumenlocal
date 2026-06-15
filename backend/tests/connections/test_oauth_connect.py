"""P1D-1 acceptance: consent URL → callback vaults token (only token_ref in DB) → import.

End-to-end over HTTP with no Postgres, no Google, and no real vault:

* ``POST /connections/oauth/start`` returns a Google consent URL carrying a signed
  ``state`` (and is RBAC-gated: 401 unauth, 403 for a role without the capability);
* ``POST /connections/oauth/callback`` exchanges the code, writes the **raw token to
  the vault only**, and persists a connection whose sole token field is the opaque
  ``token_ref`` — the raw access/refresh tokens never appear on the DB row; and
* ``POST /locations/import`` pulls the connection's GBP locations into ``locations``,
  idempotently and tenant-scoped.
"""
import asyncio
from uuid import UUID, uuid4

from app.core.security import create_oauth_state, decode_token
from app.gbp.oauth import OAuthToken
from app.security.context import RequestContext, RoleAssignment
from tests.connections.fakes import build_env

TENANT = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
OTHER_TENANT = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
CLIENT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
UNKNOWN_CLIENT = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")

CLIENT_TENANTS = {CLIENT: TENANT}


def _principal(role: str, tenant_id: UUID = TENANT) -> RequestContext:
    return RequestContext(
        user_id=uuid4(), tenant_id=tenant_id, roles=(RoleAssignment(role=role),)
    )


def _env(role: str = "account_manager", tenant_id: UUID = TENANT):
    return build_env(CLIENT_TENANTS, _principal(role, tenant_id))


# --- start ---------------------------------------------------------------------
def test_start_returns_consent_url_with_signed_state():
    env = _env()
    resp = env["client"].post(
        "/connections/oauth/start", json={"client_id": str(CLIENT)}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["consent_url"].startswith("https://")
    # The state is a signed JWT bound to the caller's tenant + client.
    claims = decode_token(body["state"])
    assert claims["type"] == "oauth_state"
    assert claims["tenant_id"] == str(TENANT)
    assert claims["client_id"] == str(CLIENT)
    assert body["state"] in body["consent_url"]  # state travels on the consent URL


def test_start_unauthenticated_401():
    env = build_env(CLIENT_TENANTS, principal=None)
    resp = env["client"].post(
        "/connections/oauth/start", json={"client_id": str(CLIENT)}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"


def test_start_forbidden_for_role_without_capability_403():
    env = _env(role="analyst")  # analyst has no connections.start
    resp = env["client"].post(
        "/connections/oauth/start", json={"client_id": str(CLIENT)}
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


def test_start_unknown_client_is_404():
    env = _env()
    resp = env["client"].post(
        "/connections/oauth/start", json={"client_id": str(UNKNOWN_CLIENT)}
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "client_not_found"


def test_start_invalid_connect_method_400():
    env = _env()
    resp = env["client"].post(
        "/connections/oauth/start",
        json={"client_id": str(CLIENT), "connect_method": "sneaky"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_connect_method"


# --- callback (the core acceptance: vault the token, DB keeps only token_ref) ---
def _connect(env, code: str = "auth-code-xyz") -> dict:
    """Run start→callback and return the callback response body."""
    state = create_oauth_state(str(TENANT), str(CLIENT), "self_serve")
    resp = env["client"].post(
        "/connections/oauth/callback", json={"code": code, "state": state}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_callback_vaults_raw_token_and_db_stores_only_ref():
    env = _env()
    code = "auth-code-xyz"
    body = _connect(env, code)

    # Response exposes connection metadata but no token material.
    assert body["token_status"] == "healthy"
    assert body["connect_method"] == "self_serve"
    assert "token" not in {k.lower() for k in body}
    assert "token_ref" not in body  # internal vault pointer is not surfaced

    # Exactly one connection persisted; its only token field is the opaque ref.
    assert len(env["store"].connections) == 1
    conn = next(iter(env["store"].connections.values()))
    assert conn.token_ref.startswith(f"gbp/{CLIENT}/")

    # The raw token lives ONLY in the vault, retrievable via the ref.
    raw = asyncio.run(env["vault"].get_secret(conn.token_ref))
    token = OAuthToken.deserialize(raw)
    assert token.access_token == f"mock-access-token-for-{code}"
    assert token.refresh_token == "mock-refresh-token"

    # The raw access/refresh tokens appear in NO persisted DB column (CLAUDE.md rule).
    persisted = {
        "token_ref": conn.token_ref,
        "connect_method": conn.connect_method,
        "token_status": conn.token_status,
        "scopes": conn.scopes,
    }
    blob = repr(persisted)
    assert token.access_token not in blob
    assert token.refresh_token not in blob


def test_callback_rejects_tampered_state_400():
    env = _env()
    resp = env["client"].post(
        "/connections/oauth/callback",
        json={"code": "x", "state": "not-a-real-jwt"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_state"


def test_callback_rejects_wrong_token_type_400():
    """A validly signed JWT that is not an oauth_state must not be accepted."""
    from app.core.security import create_access_token

    env = _env()
    not_state = create_access_token(str(uuid4()), str(TENANT))
    resp = env["client"].post(
        "/connections/oauth/callback", json={"code": "x", "state": not_state}
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_state"


# --- locations import ----------------------------------------------------------
def test_import_locations_creates_rows_tenant_scoped():
    env = _env()
    body = _connect(env)
    conn_id = next(iter(env["store"].connections))

    resp = env["client"].post(
        "/locations/import", json={"connection_id": str(conn_id)}
    )
    assert resp.status_code == 200
    out = resp.json()
    assert out["imported_count"] == 2
    assert len(out["locations"]) == 2
    assert all(loc["google_place_id"] for loc in out["locations"])

    # Persisted locations are scoped to the caller's tenant + the connection's client.
    assert len(env["store"].locations) == 2
    assert {loc.tenant_id for loc in env["store"].locations} == {TENANT}
    assert {loc.client_id for loc in env["store"].locations} == {CLIENT}


def test_import_is_idempotent_on_place_id():
    env = _env()
    _connect(env)
    conn_id = next(iter(env["store"].connections))

    first = env["client"].post("/locations/import", json={"connection_id": str(conn_id)})
    second = env["client"].post("/locations/import", json={"connection_id": str(conn_id)})
    assert first.json()["imported_count"] == 2
    assert second.json()["imported_count"] == 0  # already imported, no duplicates
    assert len(env["store"].locations) == 2


def test_import_unknown_connection_404():
    env = _env()
    resp = env["client"].post(
        "/locations/import", json={"connection_id": str(uuid4())}
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "connection_not_found"


def test_import_cross_tenant_connection_is_404():
    """A caller in another tenant cannot import a connection that isn't theirs."""
    env = _env()  # account_manager in TENANT creates the connection
    _connect(env)
    conn_id = next(iter(env["store"].connections))

    # Re-wire the same store under a caller from a different tenant.
    intruder = build_env(CLIENT_TENANTS, _principal("account_manager", OTHER_TENANT))
    intruder["service"]._store = env["store"]  # share the persisted connection
    resp = intruder["client"].post(
        "/locations/import", json={"connection_id": str(conn_id)}
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "connection_not_found"


def test_import_unauthenticated_401():
    env = build_env(CLIENT_TENANTS, principal=None)
    resp = env["client"].post(
        "/locations/import", json={"connection_id": str(uuid4())}
    )
    assert resp.status_code == 401


def test_import_forbidden_for_role_without_capability_403():
    env = _env(role="analyst")  # analyst has no locations.import
    resp = env["client"].post(
        "/locations/import", json={"connection_id": str(uuid4())}
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"
