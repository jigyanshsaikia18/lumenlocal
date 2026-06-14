"""build_matrix glue (P2B-1): grid → mock query → matrix + SoLV."""
from app.geo.scan import build_matrix


def test_matrix_has_one_entry_per_node():
    for n in (3, 5, 7):
        matrix, _ = build_matrix(40.0, -75.0, 5.0, n, "pizza")
        assert len(matrix) == n * n


def test_entry_shape():
    matrix, _ = build_matrix(40.0, -75.0, 5.0, 3, "pizza")
    entry = matrix[0]
    assert set(entry) == {"row", "col", "lat", "lon", "rank", "competitors"}
    assert entry["competitors"] == []
    assert entry["rank"] is None or 1 <= entry["rank"] <= 20


def test_deterministic_across_calls():
    a, solv_a = build_matrix(40.0, -75.0, 5.0, 5, "dentist")
    b, solv_b = build_matrix(40.0, -75.0, 5.0, 5, "dentist")
    assert a == b
    assert solv_a == solv_b


def test_different_search_terms_can_differ():
    a, _ = build_matrix(40.0, -75.0, 5.0, 5, "dentist")
    b, _ = build_matrix(40.0, -75.0, 5.0, 5, "plumber")
    assert [e["rank"] for e in a] != [e["rank"] for e in b]


def test_solv_in_range():
    _, solv = build_matrix(40.0, -75.0, 5.0, 7, "coffee")
    assert 0.0 <= solv <= 100.0
