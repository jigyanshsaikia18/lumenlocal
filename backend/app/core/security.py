"""JWT creation/verification and bcrypt password utilities.

All token operations funnel through here so algorithm and key settings stay
in one place. Call sites import named helpers, not jwt/bcrypt directly.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _encode(payload: dict, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    data = {
        **payload,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(
        data,
        settings.secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def create_access_token(user_id: str, tenant_id: str) -> str:
    return _encode(
        {"sub": user_id, "tenant_id": tenant_id, "type": "access"},
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: str, tenant_id: str) -> str:
    return _encode(
        {"sub": user_id, "tenant_id": tenant_id, "type": "refresh"},
        timedelta(days=settings.refresh_token_expire_days),
    )


def create_mfa_token(user_id: str, tenant_id: str) -> str:
    """Short-lived token issued when 2FA is required; exchanged via /auth/mfa/verify."""
    return _encode(
        {"sub": user_id, "tenant_id": tenant_id, "type": "mfa_pending"},
        timedelta(minutes=5),
    )


def create_oauth_state(
    tenant_id: str,
    client_id: str,
    connect_method: str,
    agency_gbp_project_id: str | None = None,
) -> str:
    """Signed, short-lived OAuth ``state`` for the GBP connect flow (P1D-1/P1D-2).

    Carries the scope the operator started from (tenant + client + connect method)
    so the unauthenticated Google redirect to ``/connections/oauth/callback`` can be
    bound back to it. Because it is a signed JWT, a tampered or forged ``state`` fails
    verification — this is the flow's CSRF protection, not just a nonce.

    For agency-proxy flows ``agency_gbp_project_id`` is embedded so the callback
    can persist it as proof the project-ownership rule was honoured (PRD §6.3 ON-5).
    """
    payload: dict = {
        "tenant_id": tenant_id,
        "client_id": client_id,
        "connect_method": connect_method,
        "type": "oauth_state",
    }
    if agency_gbp_project_id is not None:
        payload["agency_gbp_project_id"] = agency_gbp_project_id
    return _encode(payload, timedelta(minutes=15))


def decode_token(token: str) -> dict:
    """Decode and verify a JWT. Raises jwt.InvalidTokenError on any failure."""
    return jwt.decode(
        token,
        settings.secret_key.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
    )
