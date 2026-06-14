"""User endpoints (§2 of API spec, ticket P1B-1)."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.deps import CurrentUser
from app.schemas.auth import MeResponse, RoleOut

router = APIRouter(tags=["users"])


@router.get("/me", response_model=MeResponse)
def me(current: CurrentUser) -> MeResponse:
    """Return the authenticated user with their roles and resolved scopes."""
    user, roles = current
    return MeResponse(
        id=user.id,
        email=user.email,
        tenant_id=user.tenant_id,
        status=user.status,
        roles=[RoleOut.model_validate(r) for r in roles],
    )
