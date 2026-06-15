"""Usage-cap endpoints (API spec §4): read consumption, read/set Super-Admin caps.

The operator side of PRD §5 FT-9. ``GET /usage`` shows current consumption vs caps
for a tenant/client (the proof that metering works); ``GET/PUT /quotas`` let a
Super-Admin read and set the hard monthly limits the metered workers enforce.

The §12 chain is honoured via ``require(...)``: reading usage is ``usage.read``
(read tier), while reading and writing caps are ``quotas.read`` / ``quotas.write``
(super_admin only). The ``get_quota_service`` seam is overridden in tests so the
endpoints run without Postgres.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.db.session import get_db
from app.quotas.service import (
    SCOPE_CLIENT,
    SCOPE_TENANT,
    QuotaService,
    SqlAlchemyQuotaStore,
)
from app.schemas.quotas import (
    QuotaListResponse,
    QuotaOut,
    SetQuotaRequest,
    UsageMetricOut,
    UsageReportResponse,
)
from app.security.context import RequestContext
from app.security.deps import require

router = APIRouter(tags=["quotas"])


def get_quota_service(db: Session = Depends(get_db)) -> QuotaService:
    """Provide a request-scoped quota service over the live tables (overridden in tests)."""
    return QuotaService(SqlAlchemyQuotaStore(db))


def _validate_scope_type(scope_type: str) -> str:
    if scope_type not in (SCOPE_TENANT, SCOPE_CLIENT):
        raise APIError(
            400, "invalid_scope_type",
            f"scope_type must be '{SCOPE_TENANT}' or '{SCOPE_CLIENT}'",
            {"scope_type": scope_type},
        )
    return scope_type


@router.get("/usage", response_model=UsageReportResponse)
def get_usage(
    scope_type: str = Query(...),
    scope_id: UUID = Query(...),
    period: str | None = Query(None),  # reserved; only the active monthly period exists
    ctx: RequestContext = Depends(require("usage.read")),
    service: QuotaService = Depends(get_quota_service),
) -> UsageReportResponse:
    """Current consumption vs caps for a tenant/client (FT-9 visibility)."""
    _validate_scope_type(scope_type)
    report = service.usage_report(scope_type, scope_id)
    return UsageReportResponse(
        scope_type=scope_type,
        scope_id=scope_id,
        period_start=service.period_start(),
        metrics=[
            UsageMetricOut(
                metric=d.metric,
                used=d.used,
                limit=d.limit,
                remaining=None if d.limit is None else max(0, d.limit - d.used),
                exceeded=d.exceeded,
                on_exceed=d.on_exceed,
            )
            for d in report
        ],
    )


@router.get("/quotas", response_model=QuotaListResponse)
def list_quotas(
    scope_type: str = Query(...),
    scope_id: UUID = Query(...),
    ctx: RequestContext = Depends(require("quotas.read")),
    service: QuotaService = Depends(get_quota_service),
) -> QuotaListResponse:
    """List the Super-Admin caps configured for a scope."""
    _validate_scope_type(scope_type)
    return QuotaListResponse(
        scope_type=scope_type,
        scope_id=scope_id,
        quotas=[QuotaOut(**q.__dict__) for q in service.list_quotas(scope_type, scope_id)],
    )


@router.put("/quotas", response_model=QuotaOut)
def set_quota(
    body: SetQuotaRequest,
    scope_type: str = Query(...),
    scope_id: UUID = Query(...),
    ctx: RequestContext = Depends(require("quotas.write")),
    service: QuotaService = Depends(get_quota_service),
    db: Session = Depends(get_db),
) -> QuotaOut:
    """Set/replace a Super-Admin hard cap for one (scope, metric)."""
    _validate_scope_type(scope_type)
    try:
        quota = service.set_quota(
            scope_type, scope_id, body.metric, body.limit_value,
            period=body.period, on_exceed=body.on_exceed,
        )
    except ValueError as exc:
        raise APIError(400, "invalid_quota", str(exc)) from exc
    db.commit()
    return QuotaOut(**quota.__dict__)
