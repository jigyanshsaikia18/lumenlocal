"""The authenticated principal and how its capabilities are resolved.

``RequestContext`` is the object every handler receives once the chain in
``05_API_Specification.md §12`` has run. It answers one question for the RBAC
layer: *does this caller hold capability X (optionally, on scope Y)?*

A user may hold several role assignments at different scopes
(tenant / client / location). Capabilities are the union across assignments;
scope is enforced per assignment so a ``client_owner`` on client A is denied on
client B (RBAC-2).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from app.security.capabilities import (
    BUILTIN_ROLE_CAPABILITIES,
    WILDCARD,
    role_has_capability,
)


@dataclass(frozen=True)
class RoleAssignment:
    """One row of ``user_roles`` plus any custom-role permissions (RBAC-3).

    ``permissions`` holds capability keys granted to this (typically ``custom``)
    role via the ``role_permissions`` table. They are additive: a built-in role
    may also be extended this way.
    """

    role: str
    scope_type: str = "tenant"
    scope_id: UUID | None = None
    permissions: frozenset[str] = field(default_factory=frozenset)

    def grants(self, capability: str) -> bool:
        """True if this assignment's role (built-in bundle or custom grants) has it."""
        return role_has_capability(self.role, capability) or capability in self.permissions

    def covers(self, scope_id: UUID | None) -> bool:
        """True if this assignment's scope reaches ``scope_id``.

        A tenant-wide assignment (``scope_id is None``) covers everything in the
        tenant; a scoped assignment covers only its own scope. ``scope_id=None``
        on the query side means "no specific target" and always matches.
        """
        if scope_id is None or self.scope_id is None:
            return True
        return self.scope_id == scope_id


@dataclass(frozen=True)
class RequestContext:
    """Resolved identity for the current request."""

    user_id: UUID
    tenant_id: UUID
    roles: tuple[RoleAssignment, ...]

    def has_capability(self, capability: str, *, scope_id: UUID | None = None) -> bool:
        """True if any assignment grants ``capability`` within reach of ``scope_id``."""
        return any(
            a.grants(capability) and a.covers(scope_id) for a in self.roles
        )

    def effective_capabilities(self) -> frozenset[str]:
        """Union of capability keys this principal holds (tenant-wide view).

        Returns ``{"*"}`` for a super_admin. Useful for ``GET /me`` and for
        asserting a role's profile in tests.
        """
        out: set[str] = set()
        for a in self.roles:
            builtin = BUILTIN_ROLE_CAPABILITIES.get(a.role, frozenset())
            if WILDCARD in builtin:
                return frozenset({WILDCARD})
            out |= builtin
            out |= a.permissions
        return frozenset(out)
