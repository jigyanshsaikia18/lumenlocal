"""build_ai_matrix (P2C-2) — pure, offline. Mirrors tests/geo/test_scan.py."""
import pytest

from app.geo.ai.mock import MockAiSearchProvider
from app.geo.ai.records import Provider
from app.geo.ai_scan import build_ai_matrix

LAT, LON = 40.0, -75.0


def _scan(dimensions=5, sample_runs=1, business_name="Riverside Bistro", provider=None):
    return build_ai_matrix(
        lat=LAT,
        lon=LON,
        radius_miles=5.0,
        dimensions=dimensions,
        prompt="best bistro near me",
        business_name=business_name,
        provider=provider or MockAiSearchProvider(provider=Provider.CHATGPT),
        sample_runs=sample_runs,
    )


def test_one_entry_per_node_with_coords():
    matrix, saiv, cited = _scan(dimensions=5)
    assert len(matrix) == 25
    node = matrix[0]
    assert set(node) == {"row", "col", "lat", "lon", "runs"}
    assert isinstance(node["lat"], float) and isinstance(node["lon"], float)
    assert 0.0 <= saiv <= 100.0
    assert isinstance(cited, list)


def test_runs_per_node_matches_sample_runs():
    matrix, _, _ = _scan(dimensions=3, sample_runs=4)
    assert len(matrix) == 9
    for node in matrix:
        assert len(node["runs"]) == 4
        for run in node["runs"]:
            assert set(run) == {"mentioned", "prominence"}


def test_cited_sources_are_deduped_and_ordered():
    _, _, cited = _scan(dimensions=5, sample_runs=2)
    assert cited == list(dict.fromkeys(cited))  # no duplicates, order preserved
    assert all(isinstance(s, str) and s for s in cited)


def test_node_localization_varies_results_across_grid():
    # Different nodes get coordinate-qualified prompts, so the deterministic mock
    # does not return an identical answer at every node.
    matrix, _, _ = _scan(dimensions=5)
    signatures = {
        tuple((r["mentioned"], r["prominence"]) for r in node["runs"]) for node in matrix
    }
    assert len(signatures) > 1


def test_present_business_lifts_saiv_above_absent_one():
    # With a canned answer that names "Joe's Pizza" first, the tracked business
    # scores full visibility; a business absent from that answer scores zero.
    canned = {
        "answer": "Top picks nearby.",
        "businesses": [{"name": "Joe's Pizza", "rank": 1}],
        "sources": ["https://example.com/a"],
    }
    provider = MockAiSearchProvider(provider=Provider.CHATGPT, canned_response=canned)
    present = _scan(business_name="Joe's Pizza", provider=provider)[1]
    absent = _scan(business_name="Totally Fictional Nonexistent LLC", provider=provider)[1]
    assert present == 100.0
    assert absent == 0.0


def test_deterministic():
    a = _scan(dimensions=5, sample_runs=2)
    b = _scan(dimensions=5, sample_runs=2)
    assert a == b


def test_sample_runs_must_be_positive():
    with pytest.raises(ValueError):
        _scan(sample_runs=0)
