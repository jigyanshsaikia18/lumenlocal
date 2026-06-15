"""End-to-end regression: a real JWT reaches require()-gated routes (P1B-1/P1B-2).

This is the test the suite was missing. Every other RBAC test overrides
``get_request_context`` with a fake principal, which hid the fact that the seam
was never wired to JWT auth in the running app — so with a real token every
require()-gated route returned 401 (only /auth/* and /me worked).

These tests use the shared ``app.main:app`` (which wires ``build_request_context``
via dependency_overrides) and a *real* bearer token from /auth/login, so they
exercise the full chain: authenticate → resolve principal → capability check →
handler. They require Postgres with migrations applied.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core import token_store
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_token_store():
    token_store.clear_all()
    yield
    token_store.clear_all()


def _seed_user(role: str) -> dict:
    """Seed a tenant, a client, and an active user with ``role`` (tenant scope)."""
    tenant_id, user_id, role_id, client_id = uuid4(), uuid4(), uuid4(), uuid4()
    email = f"rbac-{user_id}@example.com"
    password = "correct-horse-battery"
    with SessionLocal() as s:
        s.execute(
            text("INSERT INTO tenants (id, company_name) VALUES (:i, :n)"),
            {"i": tenant_id, "n": "RBAC E2E Agency"},
        )
        s.execute(
            text(
                "INSERT INTO users (id, tenant_id, email, password_hash) "
                "VALUES (:i, :t, :e, :h)"
            ),
            {"i": user_id, "t": tenant_id, "e": email, "h": hash_password(password)},
        )
        s.execute(
            text(
                "INSERT INTO user_roles (id, user_id, role, scope_type) "
                "VALUES (:i, :u, :r, 'tenant')"
            ),
            {"i": role_id, "u": user_id, "r": role},
        )
        s.execute(
            text("INSERT INTO clients (id, tenant_id, name) VALUES (:i, :t, :n)"),
            {"i": client_id, "t": tenant_id, "n": "RBAC E2E Client"},
        )
        s.commit()
    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "role_id": role_id,
        "client_id": client_id,
        "email": email,
        "password": password,
    }


def _cleanup(seed: dict) -> None:
    with SessionLocal() as s:
        s.execute(text("DELETE FROM user_roles WHERE id = :id"), {"id": seed["role_id"]})
        s.execute(text("DELETE FROM users WHERE id = :id"), {"id": seed["user_id"]})
        s.execute(text("DELETE FROM clients WHERE id = :id"), {"id": seed["client_id"]})
        s.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": seed["tenant_id"]})
        s.commit()


@pytest.fixture()
def agency_admin():
    seed = _seed_user("agency_admin")
    yield seed
    _cleanup(seed)


@pytest.fixture()
def analyst():
    seed = _seed_user("analyst")
    yield seed
    _cleanup(seed)


def _login(seed: dict) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": seed["email"], "password": seed["password"]},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_valid_jwt_reaches_require_gated_route(agency_admin):
    """The regression: a real bearer token resolves a principal and passes RBAC.

    Before the seam was wired, this returned 401 despite a valid token.
    """
    token = _login(agency_admin)
    resp = client.get(
        "/api/v1/features", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), list)


def test_require_gated_route_still_401s_without_token():
    """No credentials → still 401 (the seam fails closed, never open)."""
    resp = client.get("/api/v1/features")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"


def test_capabilities_are_real_not_blanket_allow(analyst):
    """An analyst token is authenticated but lacks entitlements.override → 403.

    Proves the bridge resolves the *actual* role capabilities, not a rubber-stamp
    "any authenticated user passes" — i.e. RBAC is genuinely enforced end-to-end.
    """
    token = _login(analyst)
    resp = client.put(
        f"/api/v1/clients/{analyst['client_id']}/features/geo_ai",
        headers={"Authorization": f"Bearer {token}"},
        json={"state": True},
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["error"]["code"] == "forbidden"
