"""P2B-1 acceptance: geo-grid coordinate math against hand-computed golden values.

The golden values below were computed independently from the documented model
(equirectangular projection, EARTH_RADIUS_MILES = 3958.7613):

    DEG_PER_MILE_LAT = degrees(1 / 3958.7613)        = 0.014473158437989762
    cos(40°)                                          = 0.766044443118978
    DEG_PER_MILE_LON = DEG_PER_MILE_LAT / cos(40°)    = 0.018893366524612813

For a 3×3 grid centered at (40.0, -75.0) with radius 1 mile (node spacing = 1
mile) the rows are at +1/0/-1 mile north and the columns at -1/0/+1 mile east.
"""
import pytest

from app.geo.grid import DEG_PER_MILE_LAT, GridNode, compute_grid_nodes

# Tight tolerance: these are frozen expected coordinates, not fuzzy checks.
ABS = 1e-9


def _by_rc(nodes: list[GridNode]) -> dict[tuple[int, int], GridNode]:
    return {(n.row, n.col): n for n in nodes}


def test_3x3_golden_coordinates():
    nodes = compute_grid_nodes(40.0, -75.0, radius_miles=1.0, dimensions=3)
    assert len(nodes) == 9

    grid = _by_rc(nodes)
    # Hand-computed golden latitudes per row (north→south) ...
    north_lat = 40.01447315843799
    center_lat = 40.0
    south_lat = 39.98552684156201
    # ... and longitudes per column (west→east).
    west_lon = -75.01889336652461
    center_lon = -75.0
    east_lon = -74.98110663347539

    # North-west corner (row 0, col 0).
    assert grid[(0, 0)].lat == pytest.approx(north_lat, abs=ABS)
    assert grid[(0, 0)].lon == pytest.approx(west_lon, abs=ABS)
    # Exact center (row 1, col 1) lands on the input center.
    assert grid[(1, 1)].lat == pytest.approx(center_lat, abs=ABS)
    assert grid[(1, 1)].lon == pytest.approx(center_lon, abs=ABS)
    # South-east corner (row 2, col 2).
    assert grid[(2, 2)].lat == pytest.approx(south_lat, abs=ABS)
    assert grid[(2, 2)].lon == pytest.approx(east_lon, abs=ABS)
    # North-east / south-west corners share the right row/column.
    assert grid[(0, 2)].lat == pytest.approx(north_lat, abs=ABS)
    assert grid[(0, 2)].lon == pytest.approx(east_lon, abs=ABS)
    assert grid[(2, 0)].lat == pytest.approx(south_lat, abs=ABS)
    assert grid[(2, 0)].lon == pytest.approx(west_lon, abs=ABS)


def test_node_count_is_n_squared():
    for n in (3, 5, 7, 9, 10):
        assert len(compute_grid_nodes(40.0, -75.0, 5.0, n)) == n * n


def test_single_node_grid_is_just_the_center():
    nodes = compute_grid_nodes(12.34, 56.78, radius_miles=5.0, dimensions=1)
    assert len(nodes) == 1
    assert nodes[0] == GridNode(row=0, col=0, lat=12.34, lon=56.78)


def test_odd_grid_has_a_node_exactly_on_center():
    nodes = compute_grid_nodes(40.0, -75.0, 3.0, 5)
    mid = next(n for n in nodes if n.row == 2 and n.col == 2)
    assert mid.lat == pytest.approx(40.0, abs=ABS)
    assert mid.lon == pytest.approx(-75.0, abs=ABS)


def test_even_grid_straddles_center_with_no_node_on_it():
    nodes = compute_grid_nodes(40.0, -75.0, 3.0, 10)
    assert not any(
        n.lat == pytest.approx(40.0, abs=ABS) and n.lon == pytest.approx(-75.0, abs=ABS)
        for n in nodes
    )


def test_corners_sit_exactly_at_radius():
    # Northernmost row is +radius miles from center: Δlat == radius * DEG_PER_MILE_LAT.
    radius = 7.0
    nodes = compute_grid_nodes(40.0, -75.0, radius, 5)
    north = max(n.lat for n in nodes)
    south = min(n.lat for n in nodes)
    assert north - 40.0 == pytest.approx(radius * DEG_PER_MILE_LAT, abs=ABS)
    assert 40.0 - south == pytest.approx(radius * DEG_PER_MILE_LAT, abs=ABS)


def test_rows_evenly_spaced():
    nodes = compute_grid_nodes(40.0, -75.0, 4.0, 5)  # step = 2*4/4 = 2 miles
    lats = sorted({round(n.lat, 9) for n in nodes})
    diffs = [b - a for a, b in zip(lats, lats[1:])]
    assert all(d == pytest.approx(diffs[0], abs=ABS) for d in diffs)


def test_longitude_spread_exceeds_latitude_spread_off_equator():
    # At 40°N meridians are compressed, so a square-mile grid is wider in degrees
    # of longitude than in degrees of latitude.
    nodes = compute_grid_nodes(40.0, -75.0, 5.0, 5)
    lat_spread = max(n.lat for n in nodes) - min(n.lat for n in nodes)
    lon_spread = max(n.lon for n in nodes) - min(n.lon for n in nodes)
    assert lon_spread > lat_spread


def test_at_equator_lat_and_lon_spread_are_equal():
    # cos(0) == 1, so the degree-spread is symmetric on the equator.
    nodes = compute_grid_nodes(0.0, 0.0, 5.0, 5)
    lat_spread = max(n.lat for n in nodes) - min(n.lat for n in nodes)
    lon_spread = max(n.lon for n in nodes) - min(n.lon for n in nodes)
    assert lon_spread == pytest.approx(lat_spread, abs=ABS)


@pytest.mark.parametrize("bad_dims", [0, -1])
def test_rejects_non_positive_dimensions(bad_dims):
    with pytest.raises(ValueError):
        compute_grid_nodes(40.0, -75.0, 5.0, bad_dims)


@pytest.mark.parametrize("bad_radius", [0.0, -3.0])
def test_rejects_non_positive_radius(bad_radius):
    with pytest.raises(ValueError):
        compute_grid_nodes(40.0, -75.0, bad_radius, 5)
