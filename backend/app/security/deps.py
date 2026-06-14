"""Capability-based RBAC dependencies (chain step 2 of §12).

Usage in a route:

    @router.post("/reviews/{review_id}/reply")
    async def reply(review_id: UUID, ctx: RequestContext = Depends(require("reviews.reply"))):
        ...

``require(...)`` resolves the principal, checks the capability, and raises
``403 forbidden`` when it is missing — that is what "out-of-scope returns 403"
means. Entitlement (step 3), quota (step 4) and policy (step 5) are layered on by
later tickets (P1C+); this module owns step 2 only.

``get_request_context`` is the seam to authentication (P1B-1). Until JWT/API-key
auth lands it raises ``401``; tests and later auth code supply a principal via
``app.dependency_overrides[get_request_context]``.
"""
from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, Request

from app.core.errors import APIError
from app.security.context import RequestContext


def get_request_context() -> RequestContext:  # pragma: no cover - replaced by P1B-1
    """Resolve the authenticated principal.

    Placeholder until P1B-1 wires JWT/API-key auth. Overridden in tests and by
    the auth layer; calling it unconfigured is a 401, never an open door.
    """
    raise APIError(401, "unauthenticated", "Authentication required")


def _forbidden(capability: str) -> APIError:
    return APIError(
        403,
        "forbidden",
        "You do not have permission to perform this action",
        {"required_capability": capability},
    )


def require(
    *capabilities: str,
    scope_param: str | None = None,
) -> Callable[..., RequestContext]:
    """Build a dependency that admits only principals holding every capability.

    All listed ``capabilities`` must be held (logical AND). When ``scope_param``
    is given, it is read from the request path params and the grant must reach
    that scope (RBAC-2) — e.g. ``require("locations.write", scope_param="client_id")``.
    Returns the ``RequestContext`` so the handler can reuse it.
    """

    def dependency(
        request: Request,
        ctx: RequestContext = Depends(get_request_context),
    ) -> RequestContext:
        scope_id = _scope_from_request(request, scope_param)
        for capability in capabilities:
            if not ctx.has_capability(capability, scope_id=scope_id):
                raise _forbidden(capability)
        return ctx

    return dependency


def _scope_from_request(request: Request, scope_param: str | None) -> UUID | None:
    if scope_param is None:
        return None
    raw = request.path_params.get(scope_param)
    if raw is None:
        return None
    return raw if isinstance(raw, UUID) else UUID(str(raw))
