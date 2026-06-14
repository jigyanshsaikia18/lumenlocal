"""Pydantic schemas for auth & identity endpoints (§2 of API spec)."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
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
