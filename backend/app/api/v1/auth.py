"""Auth endpoints: login, SSO exchange, MFA verify, refresh, logout (§2, P1B-1/P1B-3)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from jwt.exceptions import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import CurrentUser, get_db
from app.core import token_store
from app.core.errors import APIError
from app.core.security import (
    create_access_token,
    create_mfa_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    MfaVerifyRequest,
    RefreshRequest,
    SsoExchangeRequest,
    TokenResponse,
)
from app.sso.registry import get_provider

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_login_response(user: User) -> LoginResponse:
    """Return either a full token pair or an MFA challenge depending on the user's 2FA flag."""
    uid, tid = str(user.id), str(user.tenant_id)
    if user.two_fa_enabled:
        return LoginResponse(
            mfa_required=True,
            mfa_token=create_mfa_token(uid, tid),
        )
    return LoginResponse(
        access_token=create_access_token(uid, tid),
        refresh_token=create_refresh_token(uid, tid),
    )


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    """Email + bcrypt password → access + refresh JWT pair (or MFA challenge).

    Returns 401 for both unknown email and wrong password (same message) to
    avoid user-enumeration via timing or response differences.
    """
    user = db.scalar(select(User).where(User.email == body.email))
    bad_creds = (
        user is None
        or not user.password_hash
        or not verify_password(body.password, user.password_hash)
    )
    if bad_creds:
        raise APIError(401, "invalid_credentials", "Email or password is incorrect")
    if user.status != "active":
        raise APIError(403, "user_inactive", "User account is suspended")

    return _issue_login_response(user)


@router.post("/sso/exchange", response_model=LoginResponse)
def sso_exchange(body: SsoExchangeRequest, db: Session = Depends(get_db)) -> LoginResponse:
    """Exchange an SSO assertion/token for a session (SAML/OIDC hook point).

    The stub provider treats the raw token value as the sso_subject.
    Replace the MockSsoProvider in app.sso.registry with a real library call.
    """
    provider = get_provider(body.provider)
    if provider is None:
        raise APIError(400, "unknown_provider", f"SSO provider '{body.provider}' is not configured")

    sso_subject = provider.exchange(body.token)
    if not sso_subject:
        raise APIError(401, "sso_token_invalid", "SSO token could not be validated")

    user = db.scalar(select(User).where(User.sso_subject == sso_subject))
    if user is None:
        raise APIError(401, "sso_user_not_found", "No user linked to this SSO subject")
    if user.status != "active":
        raise APIError(403, "user_inactive", "User account is suspended")

    return _issue_login_response(user)


@router.post("/mfa/verify", response_model=TokenResponse)
def mfa_verify(body: MfaVerifyRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Complete 2FA login: exchange mfa_token + TOTP code for a full token pair.

    The TOTP verification is stubbed — any non-empty code is accepted.
    Plug in pyotp or a real TOTP library here when 2FA is fully implemented.
    """
    try:
        payload = decode_token(body.mfa_token)
    except InvalidTokenError:
        raise APIError(401, "invalid_token", "MFA token is invalid or expired")

    if payload.get("type") != "mfa_pending":
        raise APIError(401, "invalid_token", "Not an MFA pending token")

    if not body.code:
        raise APIError(400, "mfa_code_required", "MFA code is required")

    user = db.get(User, UUID(payload["sub"]))
    if user is None or user.status != "active":
        raise APIError(401, "invalid_token", "User not found or inactive")

    uid, tid = str(user.id), str(user.tenant_id)
    return TokenResponse(
        access_token=create_access_token(uid, tid),
        refresh_token=create_refresh_token(uid, tid),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Exchange a valid refresh token for a new access + refresh pair (rotation)."""
    try:
        payload = decode_token(body.refresh_token)
    except InvalidTokenError:
        raise APIError(401, "invalid_token", "Refresh token is invalid or expired")

    if payload.get("type") != "refresh":
        raise APIError(401, "invalid_token", "Not a refresh token")

    jti = payload.get("jti", "")
    if token_store.is_revoked(jti):
        raise APIError(401, "token_revoked", "Refresh token has been revoked")

    user = db.get(User, UUID(payload["sub"]))
    if user is None or user.status != "active":
        raise APIError(401, "invalid_token", "User not found or inactive")

    token_store.revoke(jti)  # rotate: old refresh token cannot be reused
    uid, tid = str(user.id), str(user.tenant_id)
    return TokenResponse(
        access_token=create_access_token(uid, tid),
        refresh_token=create_refresh_token(uid, tid),
    )


@router.post("/logout", status_code=200)
def logout(body: RefreshRequest, _: CurrentUser) -> dict:
    """Revoke the supplied refresh token. Access token expires naturally."""
    try:
        payload = decode_token(body.refresh_token)
        jti = payload.get("jti", "")
        if jti:
            token_store.revoke(jti)
    except InvalidTokenError:
        pass  # already invalid — nothing to revoke
    return {"message": "Logged out"}
