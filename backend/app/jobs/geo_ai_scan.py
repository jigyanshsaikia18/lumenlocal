"""``run_geo_ai_scan`` — the geo-grid-for-AI visibility worker (P2C-2, flagship).

Given a location, a prompt, an AI surface, a grid size and a repeat count, this
task lays out the coordinate grid, asks the AI-search provider the prompt at each
node (``sample_runs`` times for stability — mocked, no live call yet), computes the
AI-Search Visibility (SAIV), and persists a single ``geo_ai_scans`` row with the
per-node ``matrix_results``, the rolled-up ``saiv`` and the ``cited_sources``.

It is the GEO twin of :mod:`app.jobs.geo_scan`: same P2A-1 job framework
(``base=TenantTask`` — tenant-fair, idempotent, retried, dead-lettered), same
``tenant_session`` so reads and writes are RLS-constrained to the owning tenant,
and the same **metered** discipline (PRD §5 FT-9). Before any work it consumes one
``ai_scans`` unit against the tenant's cap; a hit **pauses gracefully** (returns a
``paused`` envelope, fires no retry/dead-letter — the quota service alerts) rather
than raising.

Provider calls go through :func:`ai_provider`, a seam that today returns the
offline :class:`~app.geo.ai.mock.MockAiSearchProvider`. Real per-surface adapters
land later, under the Policy Compliance Engine and the scanning-ToS caveat
(``/docs/01_PRD.md §11.1`` — we do not claim "fully compliant" for GEO scanning).
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.celery_app import celery_app
from app.db.session import tenant_session
from app.geo.ai.base import AiSearchProvider
from app.geo.ai.mock import MockAiSearchProvider
from app.geo.ai.records import Provider
from app.geo.ai_scan import build_ai_matrix
from app.jobs.base import TENANT_TASK_OPTIONS, TenantTask
from app.models.geo_ai import GeoAiScan
from app.models.location import Location
from app.quotas.service import (
    METRIC_AI_SCANS,
    SCOPE_TENANT,
    QuotaService,
    SqlAlchemyQuotaStore,
)

_OPTS: dict[str, Any] = {**TENANT_TASK_OPTIONS, "base": TenantTask}


def quota_service(session: Any) -> QuotaService:
    """Build the metering service over the worker's tenant session.

    A seam so tests can drive the cap without Postgres (monkeypatch this name);
    in production it wraps the live ``usage_quotas`` / ``usage_counters`` tables.
    """
    return QuotaService(SqlAlchemyQuotaStore(session))


def ai_provider(provider: Provider) -> AiSearchProvider:
    """Return the adapter for an AI surface.

    A seam so tests inject a canned provider and so real per-surface adapters can
    replace the mock without touching the worker. Until live calls are wired
    (under the Policy Compliance Engine + scanning-ToS caveat), every surface
    resolves to the offline :class:`MockAiSearchProvider` labelled with ``provider``.
    """
    return MockAiSearchProvider(provider=provider)


@celery_app.task(**_OPTS)
def run_geo_ai_scan(  # noqa: ANN001 - `self` injected by bind=True
    self,
    *,
    tenant_id: str,
    location_id: str,
    prompt: str,
    provider: str,
    grid_dimensions: int = 5,
    radius_miles: float = 5.0,
    sample_runs: int = 1,
) -> dict[str, Any]:
    """Run a geo-grid-for-AI visibility scan for one location and persist it.

    Args:
        tenant_id: Owning tenant (routes fairness + scopes RLS).
        location_id: The location whose centroid (lat/lon) anchors the grid and
            whose business name is looked for in each AI answer.
        prompt: The local prompt to sample (e.g. "best plumber near me").
        provider: AI surface to query — one of the ``Provider`` enum values
            (ai_overviews / ai_mode / gemini / chatgpt / perplexity / grok).
        grid_dimensions: Grid size ``N`` → ``N × N`` nodes.
        radius_miles: Distance from the centroid to the grid edge.
        sample_runs: Repeats per node for stability (≥ 1).

    Returns:
        On success ``{"status": "ok", "scan_id", "location_id", "provider",
        "node_count", "sample_runs", "saiv", "cited_source_count"}``; when the
        tenant's ``ai_scans`` cap is hit, ``{"status": "paused",
        "reason": "quota_exceeded", "metric", "used", "limit"}`` (no scan runs and
        the op does not retry).

    Raises:
        ValueError: if ``provider`` is not a known surface, or the location is
            unknown to this tenant or has no coordinates.
    """
    try:
        surface = Provider(provider)
    except ValueError as exc:
        raise ValueError(f"unknown AI provider {provider!r}") from exc

    with tenant_session(tenant_id) as session:
        # §12 chain for a metered job: consume against the cap first. A hit pauses
        # gracefully (alert fired by the service); we do not raise, so the
        # framework neither retries nor dead-letters — no error-storm.
        decision = quota_service(session).consume(
            SCOPE_TENANT, UUID(str(tenant_id)), METRIC_AI_SCANS
        )
        if not decision.allowed:
            return {
                "status": "paused",
                "reason": "quota_exceeded",
                "metric": decision.metric,
                "location_id": location_id,
                "used": decision.used,
                "limit": decision.limit,
            }

        location = session.get(Location, location_id)
        if location is None:
            # RLS hides other tenants' locations, so "not found" is the right signal.
            raise ValueError(f"location {location_id} not found for tenant {tenant_id}")
        if location.latitude is None or location.longitude is None:
            raise ValueError(f"location {location_id} has no coordinates to scan")

        # The tracked business name lives in the GBP profile JSONB (same key the
        # locations roll-up reads); it's matched locally against each AI answer.
        business_name = (location.profile_data_live or {}).get("name", "")

        matrix, saiv, cited_sources = build_ai_matrix(
            lat=float(location.latitude),
            lon=float(location.longitude),
            radius_miles=radius_miles,
            dimensions=grid_dimensions,
            prompt=prompt,
            business_name=business_name,
            provider=ai_provider(surface),
            sample_runs=sample_runs,
        )

        scan = GeoAiScan(
            location_id=location.id,
            provider=surface.value,
            prompt=prompt,
            grid_dimensions=grid_dimensions,
            sample_runs=sample_runs,
            matrix_results=matrix,
            saiv=saiv,
            cited_sources=cited_sources,
        )
        session.add(scan)
        session.flush()  # populate scan.id before the session closes
        scan_id = str(scan.id)

    return {
        "status": "ok",
        "scan_id": scan_id,
        "location_id": location_id,
        "provider": surface.value,
        "node_count": len(matrix),
        "sample_runs": sample_runs,
        "saiv": saiv,
        "cited_source_count": len(cited_sources),
    }
