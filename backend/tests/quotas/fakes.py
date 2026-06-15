"""In-memory ``QuotaStore`` for quota tests (no Postgres).

Mirrors the semantics of ``SqlAlchemyQuotaStore`` — especially the atomic
"increment only within the cap" behaviour — over plain dicts, so ``QuotaService``
logic and the metered worker can be exercised without a database.
"""
from __future__ import annotations

from datetime import date
from uuid import UUID

from app.quotas.service import Quota

# key = (scope_type, scope_id, metric)
_QKey = tuple[str, UUID, str]
# key = (scope_type, scope_id, metric, period_start)
_CKey = tuple[str, UUID, str, date]


class FakeQuotaStore:
    def __init__(self) -> None:
        self.quotas: dict[_QKey, Quota] = {}
        self.counters: dict[_CKey, int] = {}

    # -- read ---------------------------------------------------------------
    def get_quota(self, scope_type: str, scope_id: UUID, metric: str) -> Quota | None:
        return self.quotas.get((scope_type, scope_id, metric))

    def get_used(
        self, scope_type: str, scope_id: UUID, metric: str, period_start: date
    ) -> int:
        return self.counters.get((scope_type, scope_id, metric, period_start), 0)

    # -- increment ----------------------------------------------------------
    def increment(
        self, scope_type: str, scope_id: UUID, metric: str, period_start: date, amount: int
    ) -> int:
        key = (scope_type, scope_id, metric, period_start)
        self.counters[key] = self.counters.get(key, 0) + amount
        return self.counters[key]

    def increment_within_cap(
        self,
        scope_type: str,
        scope_id: UUID,
        metric: str,
        period_start: date,
        amount: int,
        limit: int,
    ) -> int | None:
        key = (scope_type, scope_id, metric, period_start)
        current = self.counters.get(key, 0)
        if current + amount > limit:
            return None
        self.counters[key] = current + amount
        return self.counters[key]

    # -- report / admin -----------------------------------------------------
    def usage(self, scope_type: str, scope_id: UUID, period_start: date) -> dict[str, int]:
        return {
            metric: used
            for (st, sid, metric, ps), used in self.counters.items()
            if st == scope_type and sid == scope_id and ps == period_start
        }

    def list_quotas(self, scope_type: str, scope_id: UUID) -> list[Quota]:
        return [
            q for (st, sid, _m), q in self.quotas.items()
            if st == scope_type and sid == scope_id
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
        quota = Quota(
            scope_type=scope_type, scope_id=scope_id, metric=metric,
            period=period, limit_value=limit_value, on_exceed=on_exceed,
        )
        self.quotas[(scope_type, scope_id, metric)] = quota
        return quota
