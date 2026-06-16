"""Share of AI Voice — the AI-search analogue of SoLV (P2C-2).

The DB schema (``geo_ai_scans.saiv NUMERIC(5,2)``) and PRD Module 3 / GEO-1 call
for an "AI-Search Visibility" score but, like SoLV, don't pin a formula — so we
define a clear, standard one here as its own pure function, deliberately mirroring
:mod:`app.geo.solv` so the two scores read alike on the dashboard.

A geo-grid-for-AI scan produces one :class:`~app.geo.ai.records.AiVisibilityRecord`
per *sample* (one grid node, one repeated run). Each sample contributes a weight:

* **ranked mention** — the business is named at prominence ``p`` (1-based): weight
  rewards a higher position linearly, full credit at ``p == 1`` degrading to
  ``1/MAX_PROMINENCE`` at ``p == MAX_PROMINENCE`` (cf. SoLV's rank weighting).
* **buried mention** — mentioned but unranked (``prominence is None``) or ranked
  past the band: it still beats absence, so it earns the floor weight
  ``1/MAX_PROMINENCE`` — exactly a last-place ranked mention.
* **not mentioned** — weight ``0``.

SAIV is the mean weight across every sample, scaled to 0–100. So a scan whose
business is named first everywhere scores 100.00; one never named scores 0.00.

Examples:
    prominence 1 at every sample        → 100.00
    not mentioned at every sample       →   0.00
    prominence 1 at half, absent half   →  50.00
"""
from __future__ import annotations

from collections.abc import Sequence

from app.geo.ai.records import AiVisibilityRecord

DEFAULT_MAX_PROMINENCE = 10


def _weight(record: AiVisibilityRecord, max_prominence: int) -> float:
    """Visibility weight for a single sample's record, in ``[0, 1]``."""
    if not record.mentioned:
        return 0.0
    floor = 1.0 / max_prominence
    p = record.prominence
    # Buried (unranked) or ranked beyond the visible band → floor: still better
    # than being absent, no better than a last-place ranked mention.
    if p is None or p < 1 or p > max_prominence:
        return floor
    return (max_prominence - p + 1) / max_prominence


def compute_saiv(
    records: Sequence[AiVisibilityRecord],
    max_prominence: int = DEFAULT_MAX_PROMINENCE,
) -> float:
    """Compute SAIV (0–100, 2 dp) from a scan's per-sample visibility records.

    Args:
        records: One :class:`AiVisibilityRecord` per sample (grid node × run).
        max_prominence: The lowest prominence rank that still scores above the
            floor; deeper mentions earn the floor weight.

    Returns:
        AI-Search Visibility in ``[0.0, 100.0]``, rounded to two decimals. An
        empty scan scores ``0.0``.

    Raises:
        ValueError: if ``max_prominence < 1``.
    """
    if max_prominence < 1:
        raise ValueError(f"max_prominence must be >= 1, got {max_prominence}")
    if not records:
        return 0.0
    total = sum(_weight(r, max_prominence) for r in records)
    return round(100.0 * total / len(records), 2)
