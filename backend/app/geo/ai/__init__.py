"""AI-search visibility provider abstraction (P2C-1, PRD Module 3 — GEO flagship).

A provider-agnostic layer for measuring how a business shows up across AI
surfaces. Every surface gets an adapter that normalizes its native answer into
one common :class:`AiVisibilityRecord` of ``{provider, mentioned, prominence,
cited_sources}``, so the scan worker, SAIV scoring, and heatmap stay decoupled
from any one provider's quirks.

* :mod:`app.geo.ai.records` — the :class:`Provider` enum + :class:`AiVisibilityRecord`.
* :mod:`app.geo.ai.base` — the :class:`AiSearchProvider` interface.
* :mod:`app.geo.ai.mock` — :class:`MockAiSearchProvider`, the one adapter shipped
  here; real provider calls land in P2C-2.
"""
from app.geo.ai.base import AiSearchProvider
from app.geo.ai.mock import MockAiSearchProvider
from app.geo.ai.records import AiVisibilityRecord, Provider

__all__ = [
    "AiSearchProvider",
    "AiVisibilityRecord",
    "MockAiSearchProvider",
    "Provider",
]
