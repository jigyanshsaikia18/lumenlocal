"""Deterministic placeholder for the per-node Google query.

**This is a mock.** P2B-1 builds the geo-grid math and the scan worker; the real
ranking lookup is P2B-2. Until then the worker needs *something* to return a rank
per node, so this produces a stable pseudo-random rank derived from the node's
coordinates and the search term.

It performs **no** network request and talks to no external service. The real
implementation (P2B-2) must additionally respect rate limits and the relevant
scanning terms of service — see ``/docs/01_PRD.md §11.1``; this module
deliberately does none of that because it does not call anything.

Determinism matters: the same ``(node, search_term)`` always yields the same
rank, so a re-run of a scan is reproducible and tests are stable.
"""
from __future__ import annotations

import hashlib

from app.geo.grid import GridNode

# Map the hash onto ranks 1..(NOT_FOUND_THRESHOLD); values above the visible band
# are reported as "not found" (None), so a realistic share of nodes have no rank.
_RANK_SPACE = 25
_NOT_FOUND_THRESHOLD = 20


def mock_rank_for_node(node: GridNode, search_term: str) -> int | None:
    """Return a deterministic fake rank for ``node`` and ``search_term``.

    Returns an int in ``1..20`` when the (mock) business "appears", or ``None``
    when it falls outside the visible band — mimicking the not-found nodes a real
    geo-grid produces.
    """
    seed = f"{node.lat:.6f},{node.lon:.6f}|{search_term}".encode()
    digest = hashlib.sha256(seed).digest()
    # First two bytes → a stable value across the rank space.
    bucket = int.from_bytes(digest[:2], "big") % _RANK_SPACE
    rank = bucket + 1
    return rank if rank <= _NOT_FOUND_THRESHOLD else None
