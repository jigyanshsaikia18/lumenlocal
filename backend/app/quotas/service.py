"""Quota resolution + transactional consumption (PRD §5 FT-9, schema §3).

``QuotaService`` is to usage caps what ``EntitlementService`` is to feature flags:
the read/decide layer over a thin DB seam (``QuotaStore``). A metered worker calls
:meth:`QuotaService.consume` *before* doing expensive work; the service:

1. reads the Super-Admin cap for the (scope, metric) — if none, the op is
   unmetered and simply tracked;
2. **atomically** increments the current-period counter only when it stays within
   the cap (the store's ``increment_within_cap``), so concurrent workers can never
   overrun the cap (schema §8: "incremented transactionally by workers");
3. on a hard cap (``pause`` / ``block``), when the increment would exceed, it does
   **not** consume — it returns ``allowed=False`` and fires one operator alert, so
   the caller can pause gracefully instead of error-storming (FT-9);
4. on a soft cap (``alert``), it always consumes but alerts once past the cap.

The pure decision logic is unit-tested with an in-memory store + alert sink
(no Postgres); ``SqlAlchemyQuotaStore`` carries the production SQL.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.alerts import (
    SEVERITY_CRITICAL,
    SEVERITY_WARNING,
    Alert,
    AlertSink,
    alert_sink,
)

# --- The metered operations a Super-Admin can cap (schema §3 / PRD §5 FT-9) ------
METRIC_GOOGLE_API_CALLS = "google_api_calls"
METRIC_GEOGRID_SCANS = "geogrid_scans"
METRIC_AI_SCANS = "ai_scans"
METRIC_LLM_CREDITS = "llm_credits"
METERED_METRICS: frozenset[str] = frozenset(
    {METRIC_GOOGLE_API_CALLS, METRIC_GEOGRID_SCANS, METRIC_AI_SCANS, METRIC_LLM_CREDITS}
)

# --- Cap scope (schema §3: caps apply per tenant or per client) -----------------
SCOPE_TENANT = "tenant"
SCOPE_CLIENT = "client"

# --- What happens once a cap is hit (usage_quotas.on_exceed) --------------------
ON_EXCEED_PAUSE = "pause"  # default: stop the op, alert; resumes next period
ON_EXCEED_BLOCK = "block"  # hard stop (API path → 429), alert
ON_EXCEED_ALERT = "alert"  # soft cap: let it through but alert past the cap

# A hit on these modes refuses consumption (the op must not run).
_HARD_MODES: frozenset[str] = frozenset({ON_EXCEED_PAUSE, ON_EXCEED_BLOCK})

ALERT_QUOTA_EXCEEDED = "quota.exceeded"


@dataclass(frozen=True)
class Quota:
    """A resolved Super-Admin cap row (``usage_quotas``)."""

    scope_type: str
    scope_id: UUID
    metric: str
    period: str
    limit_value: int
    on_exceed: str


@dataclass(frozen=True)
class QuotaDecision:
    """Outcome of a :meth:`QuotaService.consume` call.

    ``allowed`` says whether the metered op may proceed; ``exceeded`` says whether
    this attempt hit/passed the cap. For an uncapped metric ``limit`` is ``None``
    and ``allowed`` is always ``True``. ``used`` is the counter value after the call.
    """

    metric: str
    scope_type: str
    scope_id: UUID
    period_start: date
    used: int
    limit: int | None
    allowed: bool
    exceeded: bool
    on_exceed: str | None = None


class QuotaStore(Protocol):
    """The persistence the quota service needs (mock this in tests)."""

    def get_quota(self, scope_type: str, scope_id: UUID, metric: str) -> Quota | None: ...

    def get_used(
        self, scope_type: str, scope_id: UUID, metric: str, period_start: date
    ) -> int: ...

    def increment(
        self, scope_type: str, scope_id: UUID, metric: str, period_start: date, amount: int
    ) -> int:
        """Unconditionally add ``amount``; return the new used value (upsert)."""
        ...

    def increment_within_cap(
        self,
        scope_type: str,
        scope_id: UUID,
        metric: str,
        period_start: date,
        amount: int,
        limit: int,
    ) -> int | None:
        """Atomically add ``amount`` iff it keeps used ≤ ``limit``.

        Returns the new used value, or ``None`` if the increment would exceed the
        cap (in which case nothing is consumed).
        """
        ...

    def usage(self, scope_type: str, scope_id: UUID, period_start: date) -> dict[str, int]: ...

    def list_quotas(self, scope_type: str, scope_id: UUID) -> list[Quota]: ...

    def set_quota(
        self,
        scope_type: str,
        scope_id: UUID,
        metric: str,
        limit_value: int,
        period: str,
        on_exceed: str,
    ) -> Quota: ...


def _month_start(today: date) -> date:
    """Start of the calendar month (the default monthly period anchor)."""
    return today.replace(day=1)


class QuotaService:
    """Resolve caps and consume usage, firing an alert when a cap is hit."""

    def __init__(
        self,
        store: QuotaStore,
        *,
        alerts: AlertSink | None = None,
        clock: Callable[[], date] = date.today,
    ) -> None:
        self._store = store
        self._alerts = alerts if alerts is not None else alert_sink
        self._clock = clock

    def period_start(self) -> date:
        return _month_start(self._clock())

    # -- the metered path --------------------------------------------------
    def consume(
        self, scope_type: str, scope_id: UUID, metric: str, amount: int = 1
    ) -> QuotaDecision:
        """Try to consume ``amount`` of ``metric`` for the scope, this period.

        Reads the cap, increments the counter transactionally, and decides whether
        the op may proceed. Fires one operator alert when a cap is hit.
        """
        period_start = self.period_start()
        quota = self._store.get_quota(scope_type, scope_id, metric)

        # No Super-Admin cap → unmetered, but still tracked so /usage shows it.
        if quota is None:
            used = self._store.increment(scope_type, scope_id, metric, period_start, amount)
            return QuotaDecision(
                metric=metric, scope_type=scope_type, scope_id=scope_id,
                period_start=period_start, used=used, limit=None,
                allowed=True, exceeded=False, on_exceed=None,
            )

        limit = quota.limit_value

        # Soft cap: always consume; flag (and alert) when past the limit.
        if quota.on_exceed == ON_EXCEED_ALERT:
            used = self._store.increment(scope_type, scope_id, metric, period_start, amount)
            exceeded = used > limit
            decision = QuotaDecision(
                metric=metric, scope_type=scope_type, scope_id=scope_id,
                period_start=period_start, used=used, limit=limit,
                allowed=True, exceeded=exceeded, on_exceed=quota.on_exceed,
            )
            if exceeded:
                self._alert(decision)
            return decision

        # Hard cap (pause / block): consume only if it stays within the cap.
        new_used = self._store.increment_within_cap(
            scope_type, scope_id, metric, period_start, amount, limit
        )
        if new_used is None:
            # Refused — report the current consumption (at the cap) and alert.
            current = self._store.get_used(scope_type, scope_id, metric, period_start)
            decision = QuotaDecision(
                metric=metric, scope_type=scope_type, scope_id=scope_id,
                period_start=period_start, used=current, limit=limit,
                allowed=False, exceeded=True, on_exceed=quota.on_exceed,
            )
            self._alert(decision)
            return decision

        return QuotaDecision(
            metric=metric, scope_type=scope_type, scope_id=scope_id,
            period_start=period_start, used=new_used, limit=limit,
            allowed=True, exceeded=False, on_exceed=quota.on_exceed,
        )

    def remaining(self, scope_type: str, scope_id: UUID, metric: str) -> int | None:
        """Headroom left this period, or ``None`` when the metric is uncapped."""
        quota = self._store.get_quota(scope_type, scope_id, metric)
        if quota is None:
            return None
        used = self._store.get_used(scope_type, scope_id, metric, self.period_start())
        return max(0, quota.limit_value - used)

    # -- read paths for the API (/usage, /quotas) --------------------------
    def usage_report(
        self, scope_type: str, scope_id: UUID
    ) -> list[QuotaDecision]:
        """Current consumption vs caps for every metered metric (``GET /usage``).

        Returns a read-only :class:`QuotaDecision` per metric (``allowed`` reflects
        whether headroom remains; nothing is consumed). Always reports the full
        metered-metric set so a scope with no usage yet still shows ``0`` rows.
        """
        period_start = self.period_start()
        used_by_metric = self._store.usage(scope_type, scope_id, period_start)
        quotas = {q.metric: q for q in self._store.list_quotas(scope_type, scope_id)}
        out: list[QuotaDecision] = []
        for metric in sorted(METERED_METRICS):
            used = used_by_metric.get(metric, 0)
            quota = quotas.get(metric)
            limit = quota.limit_value if quota else None
            out.append(
                QuotaDecision(
                    metric=metric, scope_type=scope_type, scope_id=scope_id,
                    period_start=period_start, used=used, limit=limit,
                    allowed=limit is None or used < limit,
                    exceeded=limit is not None and used >= limit,
                    on_exceed=quota.on_exceed if quota else None,
                )
            )
        return out

    def list_quotas(self, scope_type: str, scope_id: UUID) -> list[Quota]:
        return self._store.list_quotas(scope_type, scope_id)

    def set_quota(
        self,
        scope_type: str,
        scope_id: UUID,
        metric: str,
        limit_value: int,
        *,
        period: str = "monthly",
        on_exceed: str = ON_EXCEED_PAUSE,
    ) -> Quota:
        """Create/replace a Super-Admin cap (``PUT /quotas``). Validates inputs."""
        if metric not in METERED_METRICS:
            raise ValueError(f"unknown metric {metric!r}")
        if scope_type not in (SCOPE_TENANT, SCOPE_CLIENT):
            raise ValueError(f"unknown scope_type {scope_type!r}")
        if on_exceed not in (ON_EXCEED_PAUSE, ON_EXCEED_BLOCK, ON_EXCEED_ALERT):
            raise ValueError(f"unknown on_exceed {on_exceed!r}")
        if limit_value < 0:
            raise ValueError("limit_value must be non-negative")
        return self._store.set_quota(
            scope_type, scope_id, metric, limit_value, period, on_exceed
        )

    # -- internals ---------------------------------------------------------
    def _alert(self, d: QuotaDecision) -> None:
        severity = SEVERITY_CRITICAL if d.on_exceed in _HARD_MODES else SEVERITY_WARNING
        verb = "paused at" if d.on_exceed in _HARD_MODES else "exceeded"
        self._alerts.fire(
            Alert(
                kind=ALERT_QUOTA_EXCEEDED,
                severity=severity,
                summary=(
                    f"{d.scope_type} {d.scope_id} {verb} its '{d.metric}' "
                    f"quota ({d.used}/{d.limit} this period)"
                ),
                context={
                    "metric": d.metric,
                    "scope_type": d.scope_type,
                    "scope_id": str(d.scope_id),
                    "used": d.used,
                    "limit": d.limit,
                    "on_exceed": d.on_exceed,
                    "period_start": d.period_start.isoformat(),
                },
            )
        )


class SqlAlchemyQuotaStore:
    """Production ``QuotaStore`` over ``usage_quotas`` / ``usage_counters`` (schema §3).

    Runs as the ``lumen_app`` role (the migration grants it DML). The increment
    paths are written as atomic upserts keyed on the counter's unique constraint so
    concurrent workers cannot overrun a cap; the caller owns the transaction/commit
    (workers run inside ``tenant_session``).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_quota(self, scope_type: str, scope_id: UUID, metric: str) -> Quota | None:
        row = self._session.execute(
            text(
                "SELECT scope_type, scope_id, metric, period, limit_value, on_exceed "
                "FROM usage_quotas WHERE scope_type = :st AND scope_id = :sid AND metric = :m "
                "LIMIT 1"
            ),
            {"st": scope_type, "sid": scope_id, "m": metric},
        ).first()
        if row is None:
            return None
        return Quota(
            scope_type=row.scope_type, scope_id=row.scope_id, metric=row.metric,
            period=row.period, limit_value=row.limit_value, on_exceed=row.on_exceed,
        )

    def get_used(
        self, scope_type: str, scope_id: UUID, metric: str, period_start: date
    ) -> int:
        used = self._session.execute(
            text(
                "SELECT used_value FROM usage_counters "
                "WHERE scope_type = :st AND scope_id = :sid AND metric = :m "
                "AND period_start = :ps"
            ),
            {"st": scope_type, "sid": scope_id, "m": metric, "ps": period_start},
        ).scalar_one_or_none()
        return int(used or 0)

    def increment(
        self, scope_type: str, scope_id: UUID, metric: str, period_start: date, amount: int
    ) -> int:
        # Atomic upsert on the (scope, metric, period) unique key.
        new_used = self._session.execute(
            text(
                "INSERT INTO usage_counters "
                "(scope_type, scope_id, metric, period_start, used_value, updated_at) "
                "VALUES (:st, :sid, :m, :ps, :amt, CURRENT_TIMESTAMP) "
                "ON CONFLICT (scope_type, scope_id, metric, period_start) "
                "DO UPDATE SET used_value = usage_counters.used_value + :amt, "
                "updated_at = CURRENT_TIMESTAMP "
                "RETURNING used_value"
            ),
            {"st": scope_type, "sid": scope_id, "m": metric, "ps": period_start, "amt": amount},
        ).scalar_one()
        return int(new_used)

    def increment_within_cap(
        self,
        scope_type: str,
        scope_id: UUID,
        metric: str,
        period_start: date,
        amount: int,
        limit: int,
    ) -> int | None:
        # Two statements, one transaction: ensure the row exists at ≥0, then add
        # the amount only if it stays within the cap. The conditional UPDATE locks
        # the row and evaluates the cap atomically, so concurrent workers can never
        # push used_value past `limit`.
        self._session.execute(
            text(
                "INSERT INTO usage_counters "
                "(scope_type, scope_id, metric, period_start, used_value) "
                "VALUES (:st, :sid, :m, :ps, 0) "
                "ON CONFLICT (scope_type, scope_id, metric, period_start) DO NOTHING"
            ),
            {"st": scope_type, "sid": scope_id, "m": metric, "ps": period_start},
        )
        new_used = self._session.execute(
            text(
                "UPDATE usage_counters "
                "SET used_value = used_value + :amt, updated_at = CURRENT_TIMESTAMP "
                "WHERE scope_type = :st AND scope_id = :sid AND metric = :m "
                "AND period_start = :ps AND used_value + :amt <= :limit "
                "RETURNING used_value"
            ),
            {
                "st": scope_type, "sid": scope_id, "m": metric, "ps": period_start,
                "amt": amount, "limit": limit,
            },
        ).scalar_one_or_none()
        return None if new_used is None else int(new_used)

    def usage(self, scope_type: str, scope_id: UUID, period_start: date) -> dict[str, int]:
        rows = self._session.execute(
            text(
                "SELECT metric, used_value FROM usage_counters "
                "WHERE scope_type = :st AND scope_id = :sid AND period_start = :ps"
            ),
            {"st": scope_type, "sid": scope_id, "ps": period_start},
        )
        return {r.metric: int(r.used_value) for r in rows}

    def list_quotas(self, scope_type: str, scope_id: UUID) -> list[Quota]:
        rows = self._session.execute(
            text(
                "SELECT scope_type, scope_id, metric, period, limit_value, on_exceed "
                "FROM usage_quotas WHERE scope_type = :st AND scope_id = :sid"
            ),
            {"st": scope_type, "sid": scope_id},
        )
        return [
            Quota(
                scope_type=r.scope_type, scope_id=r.scope_id, metric=r.metric,
                period=r.period, limit_value=r.limit_value, on_exceed=r.on_exceed,
            )
            for r in rows
        ]

    def set_quota(
        self,
        scope_type: str,
        scope_id: UUID,
        metric: str,
        limit_value: int,
        period: str,
        on_exceed: str,
    ) -> Quota:
        # Upsert on the (scope, metric, period) unique key so a re-set replaces.
        self._session.execute(
            text(
                "INSERT INTO usage_quotas "
                "(scope_type, scope_id, metric, period, limit_value, on_exceed) "
                "VALUES (:st, :sid, :m, :p, :lim, :oe) "
                "ON CONFLICT (scope_type, scope_id, metric, period) "
                "DO UPDATE SET limit_value = :lim, on_exceed = :oe"
            ),
            {
                "st": scope_type, "sid": scope_id, "m": metric, "p": period,
                "lim": limit_value, "oe": on_exceed,
            },
        )
        return Quota(
            scope_type=scope_type, scope_id=scope_id, metric=metric,
            period=period, limit_value=limit_value, on_exceed=on_exceed,
        )


# Help static checkers confirm the concrete store satisfies the Protocol.
_STORE_CHECK: type[QuotaStore] = SqlAlchemyQuotaStore
