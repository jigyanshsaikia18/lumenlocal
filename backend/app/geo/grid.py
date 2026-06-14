"""Geo-grid coordinate math — the golden-tested core of P2B-1.

Given a center, a radius (the distance from center to the grid edge along the
cardinal directions) and a grid size ``N``, produce the lat/lon of every node of
an ``N × N`` square grid centered on that point.

**Projection.** We use a local *equirectangular* (flat-earth) approximation. At
local-grid scale (radii of a few to a few tens of miles) the error versus a full
geodesic is well under a meter, and the math is simple enough to hand-check —
which is exactly what the unit tests do.

* Latitude is linear in distance: ``1°`` of latitude is a fixed number of miles
  everywhere (meridians are great circles).
* Longitude is compressed toward the poles: ``1°`` of longitude spans
  ``cos(latitude)`` as many miles as it does at the equator. We evaluate that
  cosine at the **center** latitude for every column, so columns sit on constant
  meridians and the grid is a clean rectangle.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# Mean Earth radius: 6371 km / 1.609344 km·mi⁻¹.
EARTH_RADIUS_MILES = 3958.7613

# Degrees of latitude per mile along a meridian (constant). ≈ 0.0144732, i.e.
# 1° latitude ≈ 69.094 miles. Longitude divides this by cos(center latitude).
DEG_PER_MILE_LAT = math.degrees(1.0 / EARTH_RADIUS_MILES)


@dataclass(frozen=True)
class GridNode:
    """One sampling point of the geo-grid.

    ``row`` counts north→south (0 = northernmost) and ``col`` west→east
    (0 = westernmost), so ``(0, 0)`` is the north-west corner.
    """

    row: int
    col: int
    lat: float
    lon: float


def compute_grid_nodes(
    lat: float,
    lon: float,
    radius_miles: float,
    dimensions: int,
) -> list[GridNode]:
    """Compute the coordinate of every node of an ``N × N`` geo-grid.

    Args:
        lat: Center latitude in degrees.
        lon: Center longitude in degrees.
        radius_miles: Distance from the center to the grid edge (N/S/E/W). The
            grid is ``2 * radius_miles`` across; the outermost nodes sit exactly
            this far from center.
        dimensions: Grid size ``N`` (e.g. 3, 5, 7, 9, 10) → an ``N × N`` grid.

    Returns:
        ``N * N`` :class:`GridNode` in row-major order (north-west → south-east).
        For odd ``N`` the middle node lands exactly on the center; for even ``N``
        the grid straddles the center with no node on it.

    Raises:
        ValueError: if ``dimensions < 1`` or ``radius_miles <= 0``.
    """
    if dimensions < 1:
        raise ValueError(f"dimensions must be >= 1, got {dimensions}")
    if radius_miles <= 0:
        raise ValueError(f"radius_miles must be > 0, got {radius_miles}")

    # N == 1 degenerates to the center point alone (no spacing to compute).
    step_miles = 0.0 if dimensions == 1 else (2.0 * radius_miles) / (dimensions - 1)
    # Index of the center relative to the grid: offsets are taken from here, so the
    # outermost ring lands at ±radius for N>1 and the lone node sits on the center
    # for N==1 (step 0 → offset 0).
    center_index = (dimensions - 1) / 2.0

    # Longitude scale at this latitude. cos→0 only at the poles (|lat|→90), which
    # is not a real geo-grid center; guard anyway so we never divide by zero.
    cos_lat = math.cos(math.radians(lat))
    deg_per_mile_lon = DEG_PER_MILE_LAT / cos_lat if cos_lat else 0.0

    nodes: list[GridNode] = []
    for row in range(dimensions):
        # Row 0 is the northernmost (+radius); the last row is -radius.
        north_off = (center_index - row) * step_miles
        node_lat = lat + north_off * DEG_PER_MILE_LAT
        for col in range(dimensions):
            # Col 0 is the westernmost (-radius); the last col is +radius.
            east_off = (col - center_index) * step_miles
            node_lon = lon + east_off * deg_per_mile_lon
            nodes.append(GridNode(row=row, col=col, lat=node_lat, lon=node_lon))
    return nodes
