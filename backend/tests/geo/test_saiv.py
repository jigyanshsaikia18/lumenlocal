"""SAIV scorer (P2C-2) — pure, no I/O. Mirrors tests/geo/test_solv.py."""
import pytest

from app.geo.ai.records import AiVisibilityRecord, Provider
from app.geo.saiv import DEFAULT_MAX_PROMINENCE, compute_saiv


def _rec(mentioned: bool, prominence: int | None) -> AiVisibilityRecord:
    return AiVisibilityRecord(
        provider=Provider.AI_OVERVIEWS, mentioned=mentioned, prominence=prominence
    )


def test_empty_scan_scores_zero():
    assert compute_saiv([]) == 0.0


def test_top_prominence_everywhere_is_100():
    assert compute_saiv([_rec(True, 1)] * 9) == 100.00


def test_never_mentioned_is_zero():
    assert compute_saiv([_rec(False, None)] * 9) == 0.00


def test_half_top_half_absent_is_50():
    samples = [_rec(True, 1), _rec(False, None)]
    assert compute_saiv(samples) == 50.00


def test_prominence_weight_is_linear():
    # rank p weighs (MAX - p + 1)/MAX; rank 1 over MAX samples = single full point.
    one_full = [_rec(True, 1)] + [_rec(False, None)] * (DEFAULT_MAX_PROMINENCE - 1)
    assert compute_saiv(one_full) == 100.0 / DEFAULT_MAX_PROMINENCE


def test_buried_mention_earns_the_floor_not_zero():
    # Mentioned but unranked → floor weight (1/MAX), strictly above "absent".
    buried = compute_saiv([_rec(True, None)])
    assert buried == round(100.0 / DEFAULT_MAX_PROMINENCE, 2)
    assert buried > compute_saiv([_rec(False, None)])


def test_prominence_past_band_falls_to_floor():
    over = _rec(True, DEFAULT_MAX_PROMINENCE + 5)
    buried = _rec(True, None)
    assert compute_saiv([over]) == compute_saiv([buried])


def test_higher_prominence_scores_higher():
    assert compute_saiv([_rec(True, 1)]) > compute_saiv([_rec(True, 3)])


def test_invalid_max_prominence_raises():
    with pytest.raises(ValueError):
        compute_saiv([_rec(True, 1)], max_prominence=0)
