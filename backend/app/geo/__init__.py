"""Geo-grid rank tracking math (P2B-1).

Pure, dependency-free logic — no DB, no Celery — so it is fully unit-testable and
reusable by the scan worker (``app.jobs.geo_scan``) and later the heatmap UI:

* :mod:`app.geo.grid` — coordinate math: a center + radius + dimensions → the
  lat/lon of every grid node (the golden-tested core).
* :mod:`app.geo.solv` — Share-of-Local-Voice scoring from per-node ranks.
* :mod:`app.geo.mock_query` — a deterministic placeholder for the per-node
  Google query (real query is P2B-2; this does **no** network request).
* :mod:`app.geo.scan` — glue that turns a scan request into a ``matrix_results``
  payload + SoLV, ready for the worker to persist.
"""
from app.geo.grid import GridNode, compute_grid_nodes
from app.geo.mock_query import mock_rank_for_node
from app.geo.scan import build_matrix
from app.geo.solv import compute_solv

__all__ = [
    "GridNode",
    "build_matrix",
    "compute_grid_nodes",
    "compute_solv",
    "mock_rank_for_node",
]
