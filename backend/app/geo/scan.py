"""Turn a scan request into a persistable result.

This is the glue between the pure math and the worker: it lays out the grid,
queries each node (mocked for now — see :mod:`app.geo.mock_query`), and returns
the ``matrix_results`` payload plus the SoLV score. It does no I/O itself, so the
worker can be tested without a broker or a database, and the heavy logic stays
unit-testable.
"""
from __future__ import annotations

from app.geo.grid import compute_grid_nodes
from app.geo.mock_query import mock_rank_for_node
from app.geo.solv import compute_solv

# A matrix entry: one node's coordinate, the business's rank there, and the
# competitors seen at that node (empty until P2B-2 returns real results). Shape
# matches the DB schema's "Coord → rank + competitors" for geogrid_scans.matrix_results.
MatrixEntry = dict


def build_matrix(
    lat: float,
    lon: float,
    radius_miles: float,
    dimensions: int,
    search_term: str,
) -> tuple[list[MatrixEntry], float]:
    """Compute a full geo-grid scan result.

    Args:
        lat, lon: Center of the grid (the location's centroid).
        radius_miles: Distance from center to grid edge.
        dimensions: Grid size ``N`` → ``N × N`` nodes.
        search_term: The keyword being tracked.

    Returns:
        ``(matrix_results, solv)`` where ``matrix_results`` has one entry per node
        ``{"row", "col", "lat", "lon", "rank", "competitors"}`` and ``solv`` is the
        Share of Local Voice (0–100, 2 dp) across those nodes.
    """
    nodes = compute_grid_nodes(lat, lon, radius_miles, dimensions)
    matrix: list[MatrixEntry] = []
    ranks: list[int | None] = []
    for node in nodes:
        rank = mock_rank_for_node(node, search_term)
        ranks.append(rank)
        matrix.append(
            {
                "row": node.row,
                "col": node.col,
                "lat": round(node.lat, 6),
                "lon": round(node.lon, 6),
                "rank": rank,
                "competitors": [],
            }
        )
    return matrix, compute_solv(ranks)
