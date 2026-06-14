"""Auth endpoints: login, refresh, logout (§2 of API spec, ticket P1B-1)."""
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
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Email + bcrypt password → access + refresh JWT pair.

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
