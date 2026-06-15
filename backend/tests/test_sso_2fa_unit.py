"""P1B-3 unit tests: SSO entry points and 2FA two-step flow (DB-free).

Uses FastAPI dependency_overrides to inject a mock SQLAlchemy session so the
tests run without a real Postgres instance.  Covers:

  - SSO exchange endpoint exists and succeeds for a known sso_subject
  - SSO exchange returns 400 for an unknown provider
  - SSO exchange returns 401 for an empty token
  - SSO exchange returns 401 when no user matches the subject
  - Password login with two_fa_enabled=True → mfa_required=True + mfa_token
  - Password login with two_fa_enabled=False → full token pair (no MFA step)
  - SSO exchange with two_fa_enabled=True → mfa_required=True + mfa_token
  - /auth/mfa/verify with a valid mfa_pending JWT → full token pair
  - /auth/mfa/verify rejects an access token (wrong type)
  - /auth/mfa/verify rejects an empty code
"""
from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.deps import get_db
from app.core import token_store
from app.core.security import create_mfa_token, hash_password
from app.main import app
from app.models.user import User

client = TestClient(app)

# ── helpers ───────────────────────────────────────────────────────────────────

def _make_user(*, two_fa_enabled: bool = False, sso_subject: str | None = None, with_password: bool = False) -> MagicMock:
    u = MagicMock(spec=User)
    u.id = uuid4()
    u.tenant_id = uuid4()
    u.email = "testuser@example.com"
    u.status = "active"
    u.two_fa_enabled = two_fa_enabled
    u.sso_subject = sso_subject
    u.password_hash = hash_password("hunter2") if with_password else None
    return u


@pytest.fixture(autouse=True)
def _clear_token_store():
    token_store.clear_all()
    yield
    token_store.clear_all()


@pytest.fixture()
def mock_db():
    """Override get_db with a MagicMock for the duration of the test."""
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    yield db
    app.dependency_overrides.pop(get_db, None)


# ── SSO exchange ──────────────────────────────────────────────────────────────

def test_sso_exchange_endpoint_exists_and_returns_tokens(mock_db):
    subject = f"saml|{uuid4()}"
    user = _make_user(sso_subject=subject)
    mock_db.scalar.return_value = user

    resp = client.post("/api/v1/auth/sso/exchange", json={"provider": "saml", "token": subject})

    assert resp.status_code == 200
    body = resp.json()
    assert body["mfa_required"] is False
    assert body["access_token"] is not None
    assert body["refresh_token"] is not None


def test_sso_exchange_oidc_provider_also_works(mock_db):
    subject = f"oidc|{uuid4()}"
    user = _make_user(sso_subject=subject)
    mock_db.scalar.return_value = user

    resp = client.post("/api/v1/auth/sso/exchange", json={"provider": "oidc", "token": subject})
    assert resp.status_code == 200


def test_sso_exchange_unknown_provider_returns_400(mock_db):
    resp = client.post("/api/v1/auth/sso/exchange", json={"provider": "okta", "token": "x"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "unknown_provider"


def test_sso_exchange_empty_token_returns_401(mock_db):
    resp = client.post("/api/v1/auth/sso/exchange", json={"provider": "saml", "token": ""})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "sso_token_invalid"


def test_sso_exchange_no_matching_user_returns_401(mock_db):
    mock_db.scalar.return_value = None  # no user linked to this subject

    resp = client.post("/api/v1/auth/sso/exchange", json={"provider": "saml", "token": "no-such-subject"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "sso_user_not_found"


# ── 2FA: password login ───────────────────────────────────────────────────────

def test_password_login_2fa_off_returns_full_tokens(mock_db):
    user = _make_user(two_fa_enabled=False, with_password=True)
    mock_db.scalar.return_value = user

    resp = client.post("/api/v1/auth/login", json={"email": user.email, "password": "hunter2"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["mfa_required"] is False
    assert body["access_token"] is not None
    assert body["refresh_token"] is not None
    assert body["mfa_token"] is None


def test_password_login_2fa_on_returns_mfa_challenge(mock_db):
    user = _make_user(two_fa_enabled=True, with_password=True)
    mock_db.scalar.return_value = user

    resp = client.post("/api/v1/auth/login", json={"email": user.email, "password": "hunter2"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["mfa_required"] is True
    assert body["mfa_token"] is not None
    # Full tokens must NOT be present when 2FA is pending
    assert body["access_token"] is None
    assert body["refresh_token"] is None


# ── 2FA: SSO exchange ─────────────────────────────────────────────────────────

def test_sso_exchange_2fa_on_returns_mfa_challenge(mock_db):
    subject = f"saml|{uuid4()}"
    user = _make_user(sso_subject=subject, two_fa_enabled=True)
    mock_db.scalar.return_value = user

    resp = client.post("/api/v1/auth/sso/exchange", json={"provider": "saml", "token": subject})

    assert resp.status_code == 200
    body = resp.json()
    assert body["mfa_required"] is True
    assert body["mfa_token"] is not None
    assert body["access_token"] is None


# ── /auth/mfa/verify ──────────────────────────────────────────────────────────

def test_mfa_verify_completes_second_step(mock_db):
    user = _make_user(two_fa_enabled=True)
    mock_db.get.return_value = user

    mfa_tok = create_mfa_token(str(user.id), str(user.tenant_id))

    resp = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": mfa_tok, "code": "123456"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"] is not None
    assert body["refresh_token"] is not None
    assert body["token_type"] == "bearer"


def test_mfa_verify_full_flow_password_then_verify(mock_db):
    """End-to-end: login (step 1) → mfa/verify (step 2) → full tokens."""
    user = _make_user(two_fa_enabled=True, with_password=True)
    mock_db.scalar.return_value = user  # used by /auth/login
    mock_db.get.return_value = user     # used by /auth/mfa/verify

    # Step 1: password login returns challenge
    step1 = client.post("/api/v1/auth/login", json={"email": user.email, "password": "hunter2"})
    assert step1.status_code == 200
    assert step1.json()["mfa_required"] is True
    mfa_token = step1.json()["mfa_token"]

    # Step 2: verify the TOTP code (stub accepts any non-empty code)
    step2 = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": mfa_token, "code": "000000"})
    assert step2.status_code == 200
    body = step2.json()
    assert "access_token" in body
    assert "refresh_token" in body


def test_mfa_verify_rejects_wrong_token_type(mock_db):
    from app.core.security import create_access_token
    user = _make_user()
    bad_tok = create_access_token(str(user.id), str(user.tenant_id))

    resp = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": bad_tok, "code": "123456"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_token"


def test_mfa_verify_rejects_garbage_token(mock_db):
    resp = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": "not.a.jwt", "code": "123456"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_token"


def test_mfa_verify_rejects_empty_code(mock_db):
    user = _make_user()
    mfa_tok = create_mfa_token(str(user.id), str(user.tenant_id))

    resp = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": mfa_tok, "code": ""})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "mfa_code_required"
