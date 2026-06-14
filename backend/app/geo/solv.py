"""Share of Local Voice (SoLV) scoring.

The DB schema (``geogrid_scans.solv NUMERIC(5,2)``) and PRD RT-1 call for a
"Share-of-Local-Voice" metric but don't pin a formula, so we define a clear,
standard rank-weighted one here as its own pure function.

Each grid node contributes a weight that rewards higher map rankings linearly:
rank 1 is worth a full point, the weight degrades to ``1/MAX_RANK`` at rank
``MAX_RANK``, and anything below that (or "not found", represented by ``None``)
contributes nothing. SoLV is the mean weight across all nodes, scaled to 0–100.

Examples:
    rank 1 at every node            → 100.00
    not found at every node         →   0.00
    rank 1 at half, none at half    →  50.00
"""
from __future__ import annotations

from collections.abc import Sequence

DEFAULT_MAX_RANK = 20


def _weight(rank: int | None, max_rank: int) -> float:
    """Linear visibility weight for a single node's rank, in ``[0, 1]``."""
    if rank is None or rank < 1 or rank > max_rank:
        return 0.0
    return (max_rank - rank + 1) / max_rank


def compute_solv(
    ranks: Sequence[int | None],
    max_rank: int = DEFAULT_MAX_RANK,
) -> float:
    """Compute SoLV (0–100, 2 dp) from the per-node ranks of a scan.

    Args:
        ranks: One entry per grid node — the business's rank at that node, or
            ``None`` when it did not appear within ``max_rank``.
        max_rank: The lowest rank that still counts as "visible".

    Returns:
        Share of Local Voice in ``[0.0, 100.0]``, rounded to two decimals. An
        empty grid scores ``0.0``.

    Raises:
        ValueError: if ``max_rank < 1``.
    """
    if max_rank < 1:
        raise ValueError(f"max_rank must be >= 1, got {max_rank}")
    if not ranks:
        return 0.0
    total = sum(_weight(r, max_rank) for r in ranks)
    return round(100.0 * total / len(ranks), 2)
