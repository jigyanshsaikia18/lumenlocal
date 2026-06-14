"""P1B-1 acceptance: login, bad-password rejection, /me requires auth, roles.

All tests use a real Postgres connection (superuser role to seed/cleanup, the
app's TestClient for HTTP). They require the DB to be running with the schema
migrations applied.
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


@pytest.fixture()
def test_user():
    """Seed a tenant + active user with a known password; clean up after test."""
    tenant_id = uuid4()
    user_id = uuid4()
    role_id = uuid4()
    email = f"test-{user_id}@example.com"
    password = "correct-horse-battery"
    hashed = hash_password(password)

    with SessionLocal() as s:
        s.execute(
            text("INSERT INTO tenants (id, company_name) VALUES (:id, :n)"),
            {"id": tenant_id, "n": "Auth Test Agency"},
        )
        s.execute(
            text(
                "INSERT INTO users (id, tenant_id, email, password_hash) "
                "VALUES (:id, :t, :e, :h)"
            ),
            {"id": user_id, "t": tenant_id, "e": email, "h": hashed},
        )
        s.execute(
            text(
                "INSERT INTO user_roles (id, user_id, role, scope_type) "
                "VALUES (:id, :uid, :r, :st)"
            ),
            {"id": role_id, "uid": user_id, "r": "agency_admin", "st": "tenant"},
        )
        s.commit()

    yield {
        "id": user_id,
        "tenant_id": tenant_id,
        "email": email,
        "password": password,
    }

    with SessionLocal() as s:
        s.execute(text("DELETE FROM user_roles WHERE id = :id"), {"id": role_id})
        s.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        s.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})
        s.commit()


# ── Login ──────────────────────────────────────────────────────────────────────

def test_login_valid_credentials_returns_tokens(test_user):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": test_user["email"], "password": test_user["password"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


def test_login_bad_password_is_rejected(test_user):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": test_user["email"], "password": "wrong-password"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_credentials"


def test_login_unknown_email_is_rejected():
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "whatever"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_credentials"


# ── /me ───────────────────────────────────────────────────────────────────────

def test_me_requires_auth():
    resp = client.get("/api/v1/me")
    assert resp.status_code == 401


def test_me_with_invalid_token_returns_401():
    resp = client.get(
        "/api/v1/me", headers={"Authorization": "Bearer not.a.real.token"}
    )
    assert resp.status_code == 401


def test_me_returns_user_with_roles(test_user):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": test_user["email"], "password": test_user["password"]},
    )
    token = login.json()["access_token"]

    resp = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(test_user["id"])
    assert body["email"] == test_user["email"]
    assert body["tenant_id"] == str(test_user["tenant_id"])
    assert body["status"] == "active"
    assert len(body["roles"]) == 1
    assert body["roles"][0]["role"] == "agency_admin"
    assert body["roles"][0]["scope_type"] == "tenant"


# ── Refresh ───────────────────────────────────────────────────────────────────

def test_refresh_issues_new_tokens(test_user):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": test_user["email"], "password": test_user["password"]},
    )
    refresh_token = login.json()["refresh_token"]

    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body


def test_refresh_token_cannot_be_reused_after_rotation(test_user):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": test_user["email"], "password": test_user["password"]},
    )
    refresh_token = login.json()["refresh_token"]

    client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    # Second use of the same refresh token should be rejected (it was rotated/revoked)
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "token_revoked"


# ── Logout ────────────────────────────────────────────────────────────────────

def test_logout_invalidates_refresh_token(test_user):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": test_user["email"], "password": test_user["password"]},
    )
    tokens = login.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    logout = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert logout.status_code == 200

    # Refresh token should now be revoked
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "token_revoked"
