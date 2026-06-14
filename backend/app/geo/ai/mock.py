"""A mock AI-search provider — the one adapter P2C-1 ships.

**This is a mock.** It performs **no** network request and talks to no external
service (mirroring :mod:`app.geo.mock_query` on the classic-rank side). Its job
is twofold:

1. Provide a real :meth:`~AiSearchProvider.normalize` implementation against a
   representative "AI answer" payload — a synthesized answer, a ranked list of
   businesses (for prominence, GEO-4), and a list of cited sources (GEO-5).
2. Stand in for *any* surface during development: pass ``provider=`` to label the
   record, and either feed a recorded/canned payload (great for tests and replay)
   or let :meth:`fetch` synthesize a deterministic offline one from the prompt.

The real adapters (P2C-2) will parse each provider's genuine response shape, but
they emit the same :class:`AiVisibilityRecord`, so nothing downstream changes.
"""
from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

from app.geo.ai.base import AiSearchProvider
from app.geo.ai.records import AiVisibilityRecord, Provider

# A canned roster the offline fetch draws from, so a synthesized answer looks like
# a plausible "best <category> near me" response. None of these are the tracked
# business — whether the business is mentioned must come out of normalization
# honestly, not be injected by the mock.
_SAMPLE_BUSINESSES = (
    "The Corner Tap",
    "Riverside Bistro",
    "Highland Grocer",
    "Oakwood Dental Care",
    "Summit Auto Works",
)
_SAMPLE_SOURCES = (
    "https://www.yelp.com/biz/sample",
    "https://www.tripadvisor.com/sample",
    "https://www.google.com/maps/sample",
)


def _name_matches(target: str, candidate: str) -> bool:
    """True if ``target`` appears within ``candidate`` (case-insensitive).

    Substring rather than equality so a tracked "Joe's Pizza" still matches an
    answer that names "Joe's Pizza Napoletana". Empty target never matches.
    """
    t = target.strip().casefold()
    return bool(t) and t in candidate.strip().casefold()


def _clean_sources(raw_sources: Any) -> tuple[str, ...]:
    """Normalize a provider's source list to deduped, ordered URL strings.

    Tolerates the two shapes providers use: bare URL strings, or objects carrying
    the URL under ``url`` / ``href`` / ``link``. Blanks are dropped; order of
    first appearance is preserved.
    """
    if not isinstance(raw_sources, Sequence) or isinstance(raw_sources, (str, bytes)):
        return ()
    out: list[str] = []
    seen: set[str] = set()
    for item in raw_sources:
        if isinstance(item, Mapping):
            url = item.get("url") or item.get("href") or item.get("link")
        else:
            url = item
        if not url:
            continue
        url = str(url).strip()
        if url and url not in seen:
            seen.add(url)
            out.append(url)
    return tuple(out)


class MockAiSearchProvider(AiSearchProvider):
    """Offline, deterministic stand-in for any AI-search surface.

    Args:
        provider: Which surface this instance impersonates (labels the record).
        canned_response: A fixed raw payload :meth:`fetch` should return. When
            omitted, :meth:`fetch` synthesizes a deterministic payload from the
            prompt. Either way, no network is touched.

    The normalized raw shape it understands::

        {
            "answer": "free-text synthesized answer ...",
            "businesses": [{"name": "...", "rank": 1}, ...],   # ranked, optional
            "sources":   [{"url": "..."} | "https://...", ...] # optional
        }
    """

    def __init__(
        self,
        *,
        provider: Provider = Provider.AI_OVERVIEWS,
        canned_response: Mapping[str, Any] | None = None,
    ) -> None:
        self.provider = provider
        self._canned = canned_response

    def normalize(
        self,
        raw: Mapping[str, Any],
        *,
        business_name: str,
    ) -> AiVisibilityRecord:
        """Collapse the mock answer shape into an :class:`AiVisibilityRecord`."""
        businesses = raw.get("businesses") or []

        # Prominence: the rank of the first ranked entry that names the business.
        # Prefer an explicit "rank"; fall back to 1-based list position.
        prominence: int | None = None
        for position, entry in enumerate(businesses, start=1):
            name = entry.get("name", "") if isinstance(entry, Mapping) else str(entry)
            if _name_matches(business_name, name):
                rank = entry.get("rank") if isinstance(entry, Mapping) else None
                prominence = int(rank) if rank is not None else position
                break

        # Mentioned if ranked above, or named only in the free-text answer (a
        # buried mention — counts as mentioned but carries no prominence rank).
        mentioned = prominence is not None or _name_matches(
            business_name, str(raw.get("answer") or "")
        )

        return AiVisibilityRecord(
            provider=self.provider,
            mentioned=mentioned,
            prominence=prominence,
            cited_sources=_clean_sources(raw.get("sources")),
        )

    def fetch(self, prompt: str) -> Mapping[str, Any]:
        """Return a canned payload, or a deterministic synthesized one offline.

        No network request is made. The synthesized answer is stable for a given
        prompt (like :mod:`app.geo.mock_query`), so scans and tests are reproducible.
        """
        if self._canned is not None:
            return self._canned

        digest = hashlib.sha256(prompt.encode()).digest()
        # Rotate the sample roster and source list by a prompt-derived offset so
        # different prompts yield different — but stable — answers.
        offset = digest[0] % len(_SAMPLE_BUSINESSES)
        count = 1 + (digest[1] % 3)  # 1..3 businesses named
        roster = [_SAMPLE_BUSINESSES[(offset + i) % len(_SAMPLE_BUSINESSES)] for i in range(count)]
        n_sources = 1 + (digest[2] % len(_SAMPLE_SOURCES))
        return {
            "answer": f"For '{prompt}', a few well-reviewed options stand out.",
            "businesses": [{"name": name, "rank": i} for i, name in enumerate(roster, start=1)],
            "sources": list(_SAMPLE_SOURCES[:n_sources]),
        }
