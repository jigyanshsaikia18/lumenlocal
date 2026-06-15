"""Deterministic mock rank provider for keyword rank tracking (P2B-2).

Returns stable pseudo-random map-pack and organic positions derived from the
location coordinates, keyword, and device.  No network calls are made.

The real provider (a future ticket) must:
- respect the relevant search provider's rate limits and ToS;
- accept the same signature and return the same shape.

Determinism matters: the same (lat, lon, keyword, device) always yields the same
ranks so that test assertions are stable and re-runs are reproducible.
"""
from __future__ import annotations

import hashlib


# Ranks above these thresholds are reported as "not found" (None).
_MAP_PACK_VISIBLE = 3   # map pack shows 3 results
_ORGANIC_VISIBLE = 10   # first page of organic

_RANK_SPACE = 20  # total hash bucket space


def _bucket(seed: str) -> int:
    digest = hashlib.sha256(seed.encode()).digest()
    return int.from_bytes(digest[:2], "big") % _RANK_SPACE + 1


def mock_ranks(
    lat: float,
    lon: float,
    keyword: str,
    device: str,
) -> tuple[int | None, int | None]:
    """Return ``(map_pack_rank, organic_rank)`` for the given context.

    Each rank is ``1..<visible>`` when the business appears, or ``None`` when it
    falls outside the visible band — matching real-world not-found behaviour.
    """
    base = f"{lat:.6f},{lon:.6f}|{keyword}|{device}"

    map_raw = _bucket(base + "|map")
    organic_raw = _bucket(base + "|organic")

    map_pack = map_raw if map_raw <= _MAP_PACK_VISIBLE else None
    organic = organic_raw if organic_raw <= _ORGANIC_VISIBLE else None
    return map_pack, organic
