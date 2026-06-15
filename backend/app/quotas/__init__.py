"""The Super-Admin usage-cap engine (PRD §5 FT-9, schema §3).

Hard monthly caps on the expensive metered operations, composed with the
entitlement engine: feature flags answer *may this scope use a capability at all*,
quotas answer *has this scope used too much of it this period*. Metered workers
``consume`` before doing expensive work; when a cap is hit the op pauses gracefully
and an operator alert fires (never an error-storm).
"""
from app.quotas.service import (
    METERED_METRICS,
    METRIC_AI_SCANS,
    METRIC_GEOGRID_SCANS,
    METRIC_GOOGLE_API_CALLS,
    METRIC_LLM_CREDITS,
    ON_EXCEED_ALERT,
    ON_EXCEED_BLOCK,
    ON_EXCEED_PAUSE,
    SCOPE_CLIENT,
    SCOPE_TENANT,
    Quota,
    QuotaDecision,
    QuotaService,
    QuotaStore,
    SqlAlchemyQuotaStore,
)

__all__ = [
    "METERED_METRICS",
    "METRIC_AI_SCANS",
    "METRIC_GEOGRID_SCANS",
    "METRIC_GOOGLE_API_CALLS",
    "METRIC_LLM_CREDITS",
    "ON_EXCEED_ALERT",
    "ON_EXCEED_BLOCK",
    "ON_EXCEED_PAUSE",
    "SCOPE_CLIENT",
    "SCOPE_TENANT",
    "Quota",
    "QuotaDecision",
    "QuotaService",
    "QuotaStore",
    "SqlAlchemyQuotaStore",
]
