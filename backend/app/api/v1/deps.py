"""FastAPI dependency providers for auth, DB sessions, and current-user resolution.

Middleware order per §12 of API spec:
  1. Authenticate (JWT) → 401 if invalid         ← get_current_user
  2. Resolve tenant + role + scope               ← future P1B-2
  3. Entitlement check                           ← future P1C-2
  4. Quota check                                 ← future P1C-4
  5. Policy Engine (writes to Google)            ← future P3A-2
  6. Handler runs
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import token_store
from app.core.errors import APIError
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import RolePermission, User, UserRole
from app.security.context import RequestContext, RoleAssignment

# auto_error=False lets us return 401 (not 403) when credentials are absent.
_http_bearer = HTTPBearer(auto_error=False)

# Re-exported from app.db.session so existing imports (app.api.v1.deps.get_db) keep
# working; the canonical definition lives in the DB layer to avoid an import cycle
# with cross-cutting dependencies (e.g. the entitlement gateway).
__all__ = [
    "get_db",
    "get_current_user",
    "build_request_context",
    "CurrentUser",
]


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_http_bearer)],
    db: Session = Depends(get_db),
) -> tuple[User, list[UserRole]]:
    """Authenticate the request and return (user, roles).

    Raises APIError 401 on any failure so the middleware envelope is consistent.
    Uses the privileged session with an explicit tenant_id equality check —
    the RLS-scoped session is reserved for business-logic handlers.
    """
    if credentials is None:
        raise APIError(401, "unauthenticated", "Authentication required")

    try:
        payload = decode_token(credentials.credentials)
    except InvalidTokenError:
        raise APIError(401, "invalid_token", "Token is invalid or expired")

    if payload.get("type") != "access":
        raise APIError(401, "invalid_token", "Not an access token")

    jti = payload.get("jti", "")
    if token_store.is_revoked(jti):
        raise APIError(401, "token_revoked", "Token has been revoked")

    user_id_str = payload.get("sub")
    tenant_id_str = payload.get("tenant_id")
    if not user_id_str or not tenant_id_str:
        raise APIError(401, "invalid_token", "Token is missing required claims")

    user = db.get(User, UUID(user_id_str))
    if user is None or str(user.tenant_id) != tenant_id_str:
        raise APIError(401, "invalid_token", "User not found")

    if user.status != "active":
        raise APIError(401, "user_inactive", "Account is not active")

    roles = list(db.scalars(select(UserRole).where(UserRole.user_id == user.id)).all())
    return user, roles


CurrentUser = Annotated[tuple[User, list[UserRole]], Depends(get_current_user)]


def build_request_context(
    principal: CurrentUser,
    db: Session = Depends(get_db),
) -> RequestContext:
    """Bridge JWT auth (step 1) into the RBAC principal the chain consumes (step 2).

    This is the production implementation of the ``get_request_context`` seam in
    ``app.security.deps``. ``main.py`` wires it via ``dependency_overrides`` so that
    every ``require(...)``-gated route resolves a real principal from the bearer
    token — exactly as tests supply a fake one. Without this wiring the seam raises
    401 unconditionally and the entire RBAC-gated surface is unreachable.

    Custom-role grants (RBAC-3) are merged in from ``role_permissions`` so a user's
    capabilities are the union of built-in role bundles plus any custom permissions.
    """
    user, roles = principal

    # Pull custom-role permissions for exactly the roles this user holds, in one
    # query, then attach them per assignment (built-in roles simply have none).
    role_names = {r.role for r in roles}
    perms_by_role: dict[str, set[str]] = {}
    if role_names:
        rows = db.execute(
            select(RolePermission.role, RolePermission.permission).where(
                RolePermission.role.in_(role_names)
            )
        ).all()
        for role_name, permission in rows:
            perms_by_role.setdefault(role_name, set()).add(permission)

    assignments = tuple(
        RoleAssignment(
            role=r.role,
            scope_type=r.scope_type,
            scope_id=r.scope_id,
            permissions=frozenset(perms_by_role.get(r.role, ())),
        )
        for r in roles
    )
    return RequestContext(
        user_id=user.id,
        tenant_id=user.tenant_id,
        roles=assignments,
    )
