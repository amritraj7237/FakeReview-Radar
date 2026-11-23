import numpy as np
import pytest

from analysis.radar.bsi import bsi, bsi_from_shares, shrink_shares, valley_depth

BIG = 100_000  # large n so shrinkage barely matters


@pytest.mark.parametrize("shares, expected", [
    ([0.08, 0.04, 0.07, 0.17, 0.64], 0.00),   # A: normal J-shape
    ([0.28, 0.08, 0.08, 0.14, 0.42], 0.47),   # genuinely divisive
    ([0.38, 0.02, 0.02, 0.04, 0.54], 0.84),   # bimodal attack
])
def test_reference_charts(shares, expected):
    assert bsi(np.array(shares) * BIG) == pytest.approx(expected, abs=0.01)


def test_perfect_split_is_one():
    assert bsi_from_shares([0.5, 0, 0, 0, 0.5]) == pytest.approx(1.0)


def test_empty_end_means_no_valley():
    assert valley_depth(np.array([0, 0.1, 0.2, 0.3, 0.4])) == 0.0
    assert valley_depth(np.array([0.4, 0.3, 0.2, 0.1, 0])) == 0.0


def test_shrinkage_sums_to_one_and_pulls_toward_prior():
    p = shrink_shares([1, 0, 0, 0, 5])
    assert p.sum() == pytest.approx(1.0)
    assert (p > 0).all()


def test_shrinkage_calms_tiny_products():
    six = [1, 0, 0, 0, 5]
    assert bsi(six, k=0) == pytest.approx(0.556, abs=0.001)
    assert bsi(six) == pytest.approx(0.215, abs=0.001)


def test_no_reviews_returns_prior_bsi():
    assert bsi([0, 0, 0, 0, 0]) == pytest.approx(0.0)


def test_bad_input_rejected():
    with pytest.raises(ValueError):
        shrink_shares([1, 2, 3])
    with pytest.raises(ValueError):
        bsi_from_shares([0.5, 0.5, 0.5, 0, 0])
