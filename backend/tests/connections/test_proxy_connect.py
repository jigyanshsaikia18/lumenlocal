"""P1D-2 acceptance: agency-proxy connect + CSV bulk import + project-ownership guard.

Coverage:
* ``POST /connections/proxy`` returns a guided link; the signed state encodes
  ``connect_method=agency_proxy`` and the project ID.
* The project-ownership guard rejects a blank ``agency_gbp_project_id`` (400)
  and the platform's own project ID (422).
* The proxy callback stores ``agency_gbp_project_id`` on the connection.
* ``POST /locations/import/csv`` inserts locations without a GBP API call;
  idempotent on ``google_place_id``; tenant-scoped.
"""
from __future__ import annotations

import asyncio
from unittest.mock import patch
from uuid import UUID, uuid4

from app.core.security import create_oauth_state, decode_token
from app.gbp.oauth import OAuthToken
from app.security.context import RequestContext, RoleAssignment
from tests.connections.fakes import build_env

TENANT = UUID("11111111-1111-1111-1111-111111111111")
OTHER_TENANT = UUID("22222222-2222-2222-2222-222222222222")
CLIENT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
UNKNOWN_CLIENT = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")

CLIENT_TENANTS = {CLIENT: TENANT}

AGENCY_PROJECT = "agency-project-abc123"
PLATFORM_PROJECT = "lumenlocal-platform-project"


def _principal(role: str, tenant_id: UUID = TENANT) -> RequestContext:
    return RequestContext(
        user_id=uuid4(), tenant_id=tenant_id, roles=(RoleAssignment(role=role),)
    )


def _env(role: str = "agency_admin", tenant_id: UUID = TENANT):
    return build_env(CLIENT_TENANTS, _principal(role, tenant_id))


# ── proxy connect: happy path ─────────────────────────────────────────────────

def test_proxy_connect_returns_guided_link():
    env = _env()
    resp = env["client"].post(
        "/connections/proxy",
        json={"client_id": str(CLIENT), "agency_gbp_project_id": AGENCY_PROJECT},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["guided_link"].startswith("https://")
    assert "state" in body


def test_proxy_connect_state_carries_agency_proxy_method_and_project_id():
    env = _env()
    resp = env["client"].post(
        "/connections/proxy",
        json={"client_id": str(CLIENT), "agency_gbp_project_id": AGENCY_PROJECT},
    )
    assert resp.status_code == 200
    body = resp.json()
    claims = decode_token(body["state"])
    assert claims["type"] == "oauth_state"
    assert claims["connect_method"] == "agency_proxy"
    assert claims["agency_gbp_project_id"] == AGENCY_PROJECT
    assert claims["tenant_id"] == str(TENANT)
    assert claims["client_id"] == str(CLIENT)
    # The state is embedded in the guided link (CSRF protection).
    assert body["state"] in body["guided_link"]


def test_proxy_connect_forbidden_for_account_manager():
    """Only agency_admin (connections.proxy capability) may initiate proxy flows."""
    env = _env(role="account_manager")
    resp = env["client"].post(
        "/connections/proxy",
        json={"client_id": str(CLIENT), "agency_gbp_project_id": AGENCY_PROJECT},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


def test_proxy_connect_unauthenticated_401():
    env = build_env(CLIENT_TENANTS, principal=None)
    resp = env["client"].post(
        "/connections/proxy",
        json={"client_id": str(CLIENT), "agency_gbp_project_id": AGENCY_PROJECT},
    )
    assert resp.status_code == 401


def test_proxy_connect_unknown_client_is_404():
    env = _env()
    resp = env["client"].post(
        "/connections/proxy",
        json={
            "client_id": str(UNKNOWN_CLIENT),
            "agency_gbp_project_id": AGENCY_PROJECT,
        },
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "client_not_found"


# ── project-ownership guard (the hard compliance rule, PRD §6.3 ON-5) ────────

def test_project_ownership_guard_rejects_blank_project_id():
    """Blank agency_gbp_project_id must be rejected (400)."""
    env = _env()
    resp = env["client"].post(
        "/connections/proxy",
        json={"client_id": str(CLIENT), "agency_gbp_project_id": "   "},
    )
    assert resp.status_code in (400, 422), resp.text


def test_project_ownership_guard_rejects_empty_string():
    env = _env()
    resp = env["client"].post(
        "/connections/proxy",
        json={"client_id": str(CLIENT), "agency_gbp_project_id": ""},
    )
    assert resp.status_code in (400, 422), resp.text


def test_project_ownership_guard_rejects_platform_own_project():
    """An agency supplying the platform's own GBP project ID must be blocked (422).

    This documents the PRD §9.1 rule 5 guard: each agency must hold their own
    Google-approved project; they may not piggyback on the platform's project.
    The service reads ``settings.platform_gbp_project_id`` at call time, so we
    patch the setting for this test.
    """
    env = _env()
    with patch("app.connections.service.settings") as mock_settings:
        mock_settings.platform_gbp_project_id = PLATFORM_PROJECT
        resp = env["client"].post(
            "/connections/proxy",
            json={"client_id": str(CLIENT), "agency_gbp_project_id": PLATFORM_PROJECT},
        )
    assert resp.status_code == 422
    error = resp.json()["error"]
    assert error["code"] == "project_ownership_violation"


def test_project_ownership_guard_passes_for_different_project():
    """A project ID that differs from the platform's is accepted."""
    env = _env()
    with patch("app.connections.service.settings") as mock_settings:
        mock_settings.platform_gbp_project_id = PLATFORM_PROJECT
        resp = env["client"].post(
            "/connections/proxy",
            json={
                "client_id": str(CLIENT),
                "agency_gbp_project_id": "some-other-project",
            },
        )
    assert resp.status_code == 200


def test_project_ownership_guard_passes_when_platform_id_not_configured():
    """When platform_gbp_project_id is empty (default), any non-blank ID is allowed."""
    env = _env()
    with patch("app.connections.service.settings") as mock_settings:
        mock_settings.platform_gbp_project_id = ""
        resp = env["client"].post(
            "/connections/proxy",
            json={"client_id": str(CLIENT), "agency_gbp_project_id": "any-project"},
        )
    assert resp.status_code == 200


# ── proxy callback stores agency_gbp_project_id ──────────────────────────────

def test_proxy_callback_stores_agency_gbp_project_id_on_connection():
    """After the full proxy flow, connection.agency_gbp_project_id is persisted."""
    env = _env()

    # 1. Proxy connect → get signed state.
    start = env["client"].post(
        "/connections/proxy",
        json={"client_id": str(CLIENT), "agency_gbp_project_id": AGENCY_PROJECT},
    )
    assert start.status_code == 200
    state = start.json()["state"]

    # 2. Callback (as if Google redirected the client back).
    callback = env["client"].post(
        "/connections/oauth/callback",
        json={"code": "proxy-code-xyz", "state": state},
    )
    assert callback.status_code == 200
    assert callback.json()["connect_method"] == "agency_proxy"
    # The response exposes the project ID (not a secret).
    assert callback.json()["agency_gbp_project_id"] == AGENCY_PROJECT

    # 3. The persisted connection row carries the project ID as evidence.
    conn = next(iter(env["store"].connections.values()))
    assert conn.agency_gbp_project_id == AGENCY_PROJECT
    assert conn.connect_method == "agency_proxy"

    # 4. The raw token is ONLY in the vault — never on the DB row.
    raw = asyncio.run(env["vault"].get_secret(conn.token_ref))
    token = OAuthToken.deserialize(raw)
    assert token.access_token == "mock-access-token-for-proxy-code-xyz"
    assert AGENCY_PROJECT not in raw  # the project ID is not the raw token


# ── CSV bulk import ───────────────────────────────────────────────────────────

_CSV_ROWS = [
    {"google_place_id": "place-alpha", "name": "Alpha Cafe", "latitude": 37.4, "longitude": -122.1},
    {"google_place_id": "place-beta", "name": "Beta Bakery", "latitude": 37.5, "longitude": -122.2},
]


def test_csv_import_creates_locations():
    env = build_env(CLIENT_TENANTS, _principal("account_manager"))
    resp = env["client"].post(
        "/locations/import/csv",
        json={"client_id": str(CLIENT), "rows": _CSV_ROWS},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["imported_count"] == 2
    assert len(body["locations"]) == 2
    assert {loc["google_place_id"] for loc in body["locations"]} == {
        "place-alpha",
        "place-beta",
    }


def test_csv_import_is_idempotent_on_place_id():
    env = build_env(CLIENT_TENANTS, _principal("account_manager"))
    first = env["client"].post(
        "/locations/import/csv",
        json={"client_id": str(CLIENT), "rows": _CSV_ROWS},
    )
    second = env["client"].post(
        "/locations/import/csv",
        json={"client_id": str(CLIENT), "rows": _CSV_ROWS},
    )
    assert first.json()["imported_count"] == 2
    assert second.json()["imported_count"] == 0
    assert len(env["store"].locations) == 2


def test_csv_import_partial_dedup():
    """Rows that already exist are skipped; new ones are inserted."""
    env = build_env(CLIENT_TENANTS, _principal("account_manager"))
    env["client"].post(
        "/locations/import/csv",
        json={"client_id": str(CLIENT), "rows": [_CSV_ROWS[0]]},
    )
    # Second call sends both rows; only the new one should be inserted.
    resp = env["client"].post(
        "/locations/import/csv",
        json={"client_id": str(CLIENT), "rows": _CSV_ROWS},
    )
    assert resp.json()["imported_count"] == 1
    assert len(env["store"].locations) == 2


def test_csv_import_tenant_scoped():
    """A caller from another tenant cannot import into a client they don't own."""
    env = build_env(CLIENT_TENANTS, _principal("account_manager", OTHER_TENANT))
    resp = env["client"].post(
        "/locations/import/csv",
        json={"client_id": str(CLIENT), "rows": _CSV_ROWS},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "client_not_found"


def test_csv_import_unknown_client_404():
    env = build_env(CLIENT_TENANTS, _principal("account_manager"))
    resp = env["client"].post(
        "/locations/import/csv",
        json={"client_id": str(UNKNOWN_CLIENT), "rows": _CSV_ROWS},
    )
    assert resp.status_code == 404


def test_csv_import_locations_are_tenant_and_client_scoped():
    env = build_env(CLIENT_TENANTS, _principal("account_manager"))
    env["client"].post(
        "/locations/import/csv",
        json={"client_id": str(CLIENT), "rows": _CSV_ROWS},
    )
    assert all(loc.tenant_id == TENANT for loc in env["store"].locations)
    assert all(loc.client_id == CLIENT for loc in env["store"].locations)


def test_csv_import_unauthenticated_401():
    env = build_env(CLIENT_TENANTS, principal=None)
    resp = env["client"].post(
        "/locations/import/csv",
        json={"client_id": str(CLIENT), "rows": _CSV_ROWS},
    )
    assert resp.status_code == 401


def test_csv_import_forbidden_for_analyst():
    env = build_env(CLIENT_TENANTS, _principal("analyst"))
    resp = env["client"].post(
        "/locations/import/csv",
        json={"client_id": str(CLIENT), "rows": _CSV_ROWS},
    )
    assert resp.status_code == 403
