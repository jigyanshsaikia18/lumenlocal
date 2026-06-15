"""GET /audit-log — paginated read of the immutable audit trail (P1E-3, schema §7).

Returns the current tenant's audit log entries, newest-first, with optional
``action`` filtering and skip/limit pagination.

Security note: ``get_db()`` returns the privileged (superuser) session which
bypasses row-level security. The explicit ``WHERE tenant_id = :tid`` clause
using the verified ``ctx.tenant_id`` is therefore load-bearing for isolation —
it is not merely defence-in-depth here.

RBAC: ``audit_log.read`` (``analyst`` tier and above).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db
from app.schemas.audit import AuditLogEntryOut, AuditLogPage
from app.security.context import RequestContext
from app.security.deps import require

router = APIRouter(tags=["audit"])

_SELECT_COLS = (
    "id, tenant_id, actor_user_id, action, target_type, target_id, "
    "before, after, created_at"
)


@router.get("/audit-log", response_model=AuditLogPage)
def list_audit_log(
    skip: int = Query(0, ge=0, description="Entries to skip (offset)"),
    limit: int = Query(50, ge=1, le=200, description="Max entries per page"),
    action: str | None = Query(None, description="Filter by exact action key"),
    ctx: RequestContext = Depends(require("audit_log.read")),
    db: Session = Depends(get_db),
) -> AuditLogPage:
    """Return a paginated page of audit-log entries for the caller's tenant.

    Entries are ordered newest-first.  Use ``skip`` + ``limit`` for pagination.
    Optional ``action`` parameter restricts results to one action key
    (e.g. ``entitlement.override.set``).
    """
    # Build params dict shared by count and data queries.
    params: dict = {"tid": ctx.tenant_id}
    action_clause = ""
    if action is not None:
        action_clause = " AND action = :action"
        params["action"] = action

    where = f"WHERE tenant_id = :tid{action_clause}"

    total: int = db.execute(
        text(f"SELECT COUNT(*) FROM audit_log {where}"),
        params,
    ).scalar_one()

    rows = db.execute(
        text(
            f"SELECT {_SELECT_COLS} FROM audit_log {where} "
            "ORDER BY created_at DESC LIMIT :limit OFFSET :skip"
        ),
        {**params, "limit": limit, "skip": skip},
    ).mappings().all()

    return AuditLogPage(
        entries=[AuditLogEntryOut.model_validate(dict(r)) for r in rows],
        total=int(total),
        skip=skip,
        limit=limit,
    )
