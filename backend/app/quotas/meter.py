"""Credit metering scaffold: consume quota + emit an audit entry in one call (P1E-3).

``CreditMeter`` is the seam metered workers call *before* running expensive ops
(geo-grid scans, LLM calls, Google API requests).  It:

1. calls :meth:`QuotaService.consume` to atomically decrement the cap-guarded
   counter (or be denied when a hard cap is hit);
2. if the op is **allowed**, records an ``AuditLogEntry`` with
   ``action="credit.consumed"`` so every credit spend appears in the immutable
   audit trail — making consumption auditable even if the worker itself fails.

Inject :class:`InMemoryAuditLogSink` and an in-memory :class:`QuotaStore` in
tests; the production wiring uses :class:`SqlAlchemyAuditLogSink` +
:class:`SqlAlchemyQuotaStore` inside the request's ``tenant_session``.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.audit.log import AuditLogEntry, AuditLogSink
from app.quotas.service import SCOPE_TENANT, QuotaDecision, QuotaService

ACTION_CREDIT_CONSUMED = "credit.consumed"


@dataclass(frozen=True)
class MeterResult:
    """Outcome of :meth:`CreditMeter.consume`.

    ``allowed`` mirrors ``QuotaDecision.allowed``.  When ``False`` the caller
    must not proceed with the expensive op.  ``decision`` carries the full
    quota context (used / limit / on_exceed) for logging or HTTP responses.
    """

    decision: QuotaDecision
    allowed: bool


class CreditMeter:
    """Combine quota enforcement with audit-log recording for every metered op.

    Usage::

        meter = CreditMeter(quota_service, audit_sink)
        result = meter.consume(
            tenant_id=ctx.tenant_id,
            actor_user_id=ctx.user_id,
            scope_id=ctx.tenant_id,   # or a client_id for client-scoped caps
            metric=METRIC_GEOGRID_SCANS,
            target_type="location",
            target_id=location_id,
        )
        if not result.allowed:
            raise APIError(429, "quota_exceeded", "Monthly scan quota reached")
        # ... run the expensive work ...
    """

    def __init__(self, quota_service: QuotaService, audit_sink: AuditLogSink) -> None:
        self._quotas = quota_service
        self._audit = audit_sink

    def consume(
        self,
        *,
        tenant_id: UUID,
        scope_id: UUID,
        metric: str,
        actor_user_id: UUID | None = None,
        scope_type: str = SCOPE_TENANT,
        amount: int = 1,
        target_type: str | None = None,
        target_id: UUID | None = None,
    ) -> MeterResult:
        """Consume ``amount`` of ``metric`` and audit if the op is allowed.

        The audit entry is written only when the quota service permits the op
        (``QuotaDecision.allowed is True``).  On a hard cap refusal the caller
        receives ``MeterResult.allowed = False`` and no audit row is written —
        the quota-exceeded alert from :class:`QuotaService` serves as the
        operator signal instead.
        """
        decision = self._quotas.consume(scope_type, scope_id, metric, amount)

        if decision.allowed:
            self._audit.record(
                AuditLogEntry(
                    tenant_id=tenant_id,
                    actor_user_id=actor_user_id,
                    action=ACTION_CREDIT_CONSUMED,
                    target_type=target_type,
                    target_id=target_id,
                    after={
                        "metric": metric,
                        "amount": amount,
                        "used": decision.used,
                        "limit": decision.limit,
                        "scope_type": scope_type,
                        "scope_id": str(scope_id),
                    },
                )
            )

        return MeterResult(decision=decision, allowed=decision.allowed)
