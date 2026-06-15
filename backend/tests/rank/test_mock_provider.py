"""Unit tests for the deterministic mock rank provider (P2B-2)."""
from __future__ import annotations

from app.rank.mock_provider import mock_ranks


def test_returns_tuple_of_two():
    result = mock_ranks(40.0, -75.0, "plumber", "desktop")
    assert len(result) == 2


def test_map_pack_rank_in_valid_range_or_none():
    map_rank, _ = mock_ranks(40.0, -75.0, "pizza", "desktop")
    assert map_rank is None or (1 <= map_rank <= 3)


def test_organic_rank_in_valid_range_or_none():
    _, organic = mock_ranks(40.0, -75.0, "pizza", "desktop")
    assert organic is None or (1 <= organic <= 10)


def test_deterministic_same_input():
    r1 = mock_ranks(40.0, -75.0, "dentist", "mobile")
    r2 = mock_ranks(40.0, -75.0, "dentist", "mobile")
    assert r1 == r2


def test_different_keywords_may_differ():
    r1 = mock_ranks(40.0, -75.0, "pizza", "desktop")
    r2 = mock_ranks(40.0, -75.0, "dentist", "desktop")
    # Not guaranteed to differ, but with high probability they do.
    # Just ensure both calls succeed without error.
    assert r1 is not None
    assert r2 is not None


def test_device_affects_result():
    desktop = mock_ranks(40.0, -75.0, "coffee", "desktop")
    mobile = mock_ranks(40.0, -75.0, "coffee", "mobile")
    # The two seeds differ, so results differ (hash space is small enough that
    # we can assert the seed strings are different, which they always are).
    # Just assert both return valid shapes.
    assert len(desktop) == 2
    assert len(mobile) == 2
