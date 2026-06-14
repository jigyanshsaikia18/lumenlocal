"""The normalized record every AI-search provider collapses down to (P2C-1).

PRD Module 3 (the GEO flagship) tracks visibility across a heterogeneous and
*extensible* set of AI surfaces — Google AI Overviews, AI Mode, Gemini, ChatGPT,
Perplexity, Grok (GEO-2). Each speaks a different native response shape. Rather
than let those shapes leak into the rest of the pipeline, every provider adapter
normalizes its answer into the single :class:`AiVisibilityRecord` below, so the
scan worker, the SAIV scorer (GEO-1), and the heatmap UI stay provider-agnostic.

The record carries exactly the fields P2C-1 calls for:

* ``provider``     — which AI surface produced this (matches the DB enum values).
* ``mentioned``    — did the business appear in the answer at all (GEO-1).
* ``prominence``   — pseudo-rank / order of the business within the answer
  (first-mention vs. buried), the proxy ranking of GEO-4. ``None`` when the
  business is absent, or present but unranked (a buried free-text mention).
* ``cited_sources``— the third-party sources the AI referenced (GEO-5), so the
  agency learns where to invest. Captured even when the business is *not*
  mentioned, since "who is cited for this category" is itself the signal.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Provider(str, Enum):
    """The AI surfaces tracked for visibility (PRD GEO-2).

    Values are the exact strings stored in ``geo_ai_scans.provider`` (see
    ``/docs/04_Database_Schema.md``), so a record serializes straight to the DB.
    The set is intentionally extensible — adding a surface is one enum member
    plus one :class:`~app.geo.ai.base.AiSearchProvider` adapter.
    """

    AI_OVERVIEWS = "ai_overviews"
    AI_MODE = "ai_mode"
    GEMINI = "gemini"
    CHATGPT = "chatgpt"
    PERPLEXITY = "perplexity"
    GROK = "grok"


@dataclass(frozen=True)
class AiVisibilityRecord:
    """One provider's normalized answer about one business for one prompt.

    Invariants (enforced by the normalizing adapters, not this class):

    * ``prominence`` is ``None`` whenever ``mentioned`` is ``False``.
    * a non-``None`` ``prominence`` is a 1-based rank — ``1`` is the most
      prominent (first) mention; larger is more buried.
    """

    provider: Provider
    mentioned: bool
    prominence: int | None
    cited_sources: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        """Render to the JSON-friendly shape stored in ``matrix_results``.

        ``provider`` becomes its plain string value and ``cited_sources`` a list,
        so the result drops straight into the ``geo_ai_scans`` JSONB columns.
        """
        return {
            "provider": self.provider.value,
            "mentioned": self.mentioned,
            "prominence": self.prominence,
            "cited_sources": list(self.cited_sources),
        }
