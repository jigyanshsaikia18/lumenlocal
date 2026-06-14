"""SoLV scoring (P2B-1)."""
import pytest

from app.geo.solv import compute_solv


def test_rank_one_everywhere_is_100():
    assert compute_solv([1] * 9) == 100.0


def test_not_found_everywhere_is_zero():
    assert compute_solv([None] * 9) == 0.0


def test_empty_grid_is_zero():
    assert compute_solv([]) == 0.0


def test_half_rank_one_half_missing_is_50():
    assert compute_solv([1, 1, None, None]) == 50.0


def test_mixed_ranks_hand_computed():
    # weights at max_rank=20: rank1=20/20=1.0, rank10=11/20=0.55, rank20=1/20=0.05,
    # not-found=0. mean = (1.0 + 0.55 + 0.05 + 0) / 4 = 0.4 → 40.00.
    assert compute_solv([1, 10, 20, None]) == 40.0


def test_ranks_beyond_max_rank_score_zero():
    assert compute_solv([21, 100]) == 0.0


def test_result_is_bounded_and_two_decimals():
    solv = compute_solv([3, 7, 11, 15, 19, None, 2])
    assert 0.0 <= solv <= 100.0
    assert round(solv, 2) == solv


def test_custom_max_rank():
    # max_rank=3: rank1=3/3=1.0, rank3=1/3≈0.333 → mean = (1.0+0.3333)/2 = 0.6667 → 66.67
    assert compute_solv([1, 3], max_rank=3) == 66.67


def test_rejects_bad_max_rank():
    with pytest.raises(ValueError):
        compute_solv([1], max_rank=0)
