"""P1B-3 acceptance tests: SSO hook points and 2FA flag.

Coverage:
- Password login returns MFA challenge when two_fa_enabled=True
- SSO exchange succeeds via mocked provider (sso_subject lookup)
- SSO login with 2FA flag also triggers MFA challenge
- /auth/mfa/verify completes login with a valid mfa_token
- /auth/mfa/verify rejects an invalid/wrong-type token
- Unknown SSO provider returns 400
- Unknown SSO subject returns 401
- Empty SSO token returns 401
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core import token_store
from app.core.security import create_mfa_token, hash_password
from app.db.session import SessionLocal
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_token_store():
    token_store.clear_all()
    yield
    token_store.clear_all()


def _seed_user(
    *,
    two_fa_enabled: bool = False,
    sso_subject: str | None = None,
    password: str | None = "hunter2",
) -> dict:
    tenant_id = uuid4()
    user_id = uuid4()
    email = f"sso2fa-{user_id}@example.com"
    hashed = hash_password(password) if password else None

    with SessionLocal() as s:
        s.execute(
            text("INSERT INTO tenants (id, company_name) VALUES (:id, :n)"),
            {"id": tenant_id, "n": "SSO Test Agency"},
        )
        s.execute(
            text(
                "INSERT INTO users "
                "(id, tenant_id, email, password_hash, sso_subject, two_fa_enabled) "
                "VALUES (:id, :t, :e, :h, :s, :f)"
            ),
            {
                "id": user_id,
                "t": tenant_id,
                "e": email,
                "h": hashed,
                "s": sso_subject,
                "f": two_fa_enabled,
            },
        )
        s.commit()

    return {"id": user_id, "tenant_id": tenant_id, "email": email, "password": password, "sso_subject": sso_subject}


def _cleanup(user: dict) -> None:
    with SessionLocal() as s:
        s.execute(text("DELETE FROM users WHERE id = :id"), {"id": user["id"]})
        s.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": user["tenant_id"]})
        s.commit()


# ── Password login + 2FA ──────────────────────────────────────────────────────

def test_login_2fa_disabled_returns_full_tokens():
    user = _seed_user(two_fa_enabled=False)
    try:
        resp = client.post("/api/v1/auth/login", json={"email": user["email"], "password": user["password"]})
        assert resp.status_code == 200
        body = resp.json()
        assert body["mfa_required"] is False
        assert body["access_token"] is not None
        assert body["refresh_token"] is not None
        assert body["mfa_token"] is None
    finally:
        _cleanup(user)


def test_login_2fa_enabled_returns_mfa_challenge():
    user = _seed_user(two_fa_enabled=True)
    try:
        resp = client.post("/api/v1/auth/login", json={"email": user["email"], "password": user["password"]})
        assert resp.status_code == 200
        body = resp.json()
        assert body["mfa_required"] is True
        assert body["mfa_token"] is not None
        assert body["access_token"] is None
        assert body["refresh_token"] is None
    finally:
        _cleanup(user)


def test_login_2fa_enabled_does_not_leak_full_tokens():
    """Access+refresh tokens must be absent when 2FA is pending."""
    user = _seed_user(two_fa_enabled=True)
    try:
        resp = client.post("/api/v1/auth/login", json={"email": user["email"], "password": user["password"]})
        body = resp.json()
        assert "access_token" not in body or body["access_token"] is None
        assert "refresh_token" not in body or body["refresh_token"] is None
    finally:
        _cleanup(user)


# ── /auth/mfa/verify ──────────────────────────────────────────────────────────

def test_mfa_verify_with_valid_token_returns_full_tokens():
    user = _seed_user(two_fa_enabled=True)
    try:
        # Step 1: get MFA challenge
        resp = client.post("/api/v1/auth/login", json={"email": user["email"], "password": user["password"]})
        mfa_token = resp.json()["mfa_token"]

        # Step 2: verify — stub accepts any non-empty code
        resp2 = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": mfa_token, "code": "123456"})
        assert resp2.status_code == 200
        body = resp2.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"
    finally:
        _cleanup(user)


def test_mfa_verify_rejects_wrong_token_type():
    """A normal access token must not be accepted at /auth/mfa/verify."""
    from app.core.security import create_access_token
    user = _seed_user(two_fa_enabled=True)
    try:
        bad_token = create_access_token(str(user["id"]), str(user["tenant_id"]))
        resp = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": bad_token, "code": "123456"})
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "invalid_token"
    finally:
        _cleanup(user)


def test_mfa_verify_rejects_garbage_token():
    resp = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": "not.a.token", "code": "123456"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_token"


def test_mfa_verify_rejects_empty_code():
    user = _seed_user(two_fa_enabled=True)
    try:
        mfa_tok = create_mfa_token(str(user["id"]), str(user["tenant_id"]))
        resp = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": mfa_tok, "code": ""})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "mfa_code_required"
    finally:
        _cleanup(user)


# ── SSO exchange ──────────────────────────────────────────────────────────────

def test_sso_exchange_succeeds_for_known_subject():
    subject = f"saml|{uuid4()}"
    user = _seed_user(sso_subject=subject, password=None)
    try:
        resp = client.post("/api/v1/auth/sso/exchange", json={"provider": "saml", "token": subject})
        assert resp.status_code == 200
        body = resp.json()
        assert body["mfa_required"] is False
        assert body["access_token"] is not None
    finally:
        _cleanup(user)


def test_sso_exchange_oidc_provider_works():
    subject = f"oidc|{uuid4()}"
    user = _seed_user(sso_subject=subject, password=None)
    try:
        resp = client.post("/api/v1/auth/sso/exchange", json={"provider": "oidc", "token": subject})
        assert resp.status_code == 200
    finally:
        _cleanup(user)


def test_sso_exchange_with_2fa_returns_mfa_challenge():
    subject = f"saml|{uuid4()}"
    user = _seed_user(sso_subject=subject, two_fa_enabled=True, password=None)
    try:
        resp = client.post("/api/v1/auth/sso/exchange", json={"provider": "saml", "token": subject})
        assert resp.status_code == 200
        body = resp.json()
        assert body["mfa_required"] is True
        assert body["mfa_token"] is not None
        assert body["access_token"] is None
    finally:
        _cleanup(user)


def test_sso_exchange_unknown_subject_returns_401():
    resp = client.post("/api/v1/auth/sso/exchange", json={"provider": "saml", "token": "no-such-subject"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "sso_user_not_found"


def test_sso_exchange_unknown_provider_returns_400():
    resp = client.post("/api/v1/auth/sso/exchange", json={"provider": "okta", "token": "anything"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "unknown_provider"


def test_sso_exchange_empty_token_returns_401():
    resp = client.post("/api/v1/auth/sso/exchange", json={"provider": "saml", "token": ""})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "sso_token_invalid"


# ── Backward-compat: existing /auth/login tests still work ───────────────────

def test_login_non_2fa_user_still_returns_access_token():
    """Regression guard: non-2FA users get tokens, not an MFA challenge."""
    user = _seed_user(two_fa_enabled=False)
    try:
        resp = client.post("/api/v1/auth/login", json={"email": user["email"], "password": user["password"]})
        assert resp.status_code == 200
        assert resp.json()["access_token"] is not None
    finally:
        _cleanup(user)
