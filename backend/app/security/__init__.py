"""Identity & RBAC (capability-based access control).

Public surface:
- ``require`` / ``get_request_context`` — FastAPI dependencies (chain step 2).
- ``RequestContext`` / ``RoleAssignment`` — the resolved principal.
- ``role_has_capability`` / ``CAPABILITY_CATALOG`` — the capability registry.
"""
from app.security.capabilities import (
    BUILTIN_ROLE_CAPABILITIES,
    CAPABILITY_CATALOG,
    is_known_capability,
    role_has_capability,
)
from app.security.context import RequestContext, RoleAssignment
from app.security.deps import get_request_context, require

__all__ = [
    "BUILTIN_ROLE_CAPABILITIES",
    "CAPABILITY_CATALOG",
    "RequestContext",
    "RoleAssignment",
    "get_request_context",
    "is_known_capability",
    "require",
    "role_has_capability",
]
