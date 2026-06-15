"""Pydantic schemas for auth & identity endpoints (§2 of API spec)."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class SsoExchangeRequest(BaseModel):
    provider: str   # "saml" | "oidc"
    token: str      # raw assertion / id_token (stub: treated as sso_subject)


class MfaVerifyRequest(BaseModel):
    mfa_token: str
    code: str       # 6-digit TOTP code (stub: any non-empty value accepted)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginResponse(BaseModel):
    """Returned by /auth/login and /auth/sso/exchange.

    When mfa_required=True only mfa_token is set; the caller must POST to
    /auth/mfa/verify with the MFA code to receive the full token pair.
    """

    mfa_required: bool = False
    mfa_token: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class RoleOut(BaseModel):
    role: str
    scope_type: str
    scope_id: UUID | None = None

    model_config = {"from_attributes": True}


class MeResponse(BaseModel):
    id: UUID
    email: str
    tenant_id: UUID
    status: str
    roles: list[RoleOut]
