import math

import numpy as np
import pytest
from scipy import stats

from analysis.radar.metrics import (
    counts_from_ratings, kurtosis, mean_and_variance, rating_metrics,
    shares_from_ratings, skewness,
)

A = [0.08, 0.04, 0.07, 0.17, 0.64]   # normal J-shape
B = [0.38, 0.02, 0.02, 0.04, 0.54]   # bimodal attack
C = [0.20, 0.20, 0.20, 0.20, 0.20]   # flat
DIVISIVE = [0.28, 0.08, 0.08, 0.14, 0.42]


@pytest.mark.parametrize("shares, mean, variance", [
    (A, 4.25, 1.5275),     # worked out on paper, see docs/METRICS.md
    (B, 3.34, 3.6244),
    (C, 3.00, 2.0000),
    (DIVISIVE, 3.34, 2.9044),
])
def test_paper_answers(shares, mean, variance):
    m, v = mean_and_variance(shares)
    assert m == pytest.approx(mean)
    assert v == pytest.approx(variance)


@pytest.mark.parametrize("shares", [A, B, C, DIVISIVE])
def test_matches_scipy_on_100_expanded_ratings(shares):
    ratings = np.repeat([1, 2, 3, 4, 5], np.round(np.array(shares) * 100).astype(int))
    assert len(ratings) == 100
    assert skewness(shares) == pytest.approx(stats.skew(ratings))
    assert kurtosis(shares) == pytest.approx(stats.kurtosis(ratings))


def test_known_signs():
    assert skewness(A) < 0          # J-shape: long tail toward 1 star
    assert kurtosis(B) < 0          # two ends, empty middle
    assert skewness(C) == pytest.approx(0.0)
    assert kurtosis(C) == pytest.approx(-1.3)


def test_variance_never_above_4():
    _, v = mean_and_variance([0.5, 0, 0, 0, 0.5])
    assert v == pytest.approx(4.0)


def test_all_same_star_gives_nan_shape():
    m = rating_metrics([0, 0, 0, 0, 1])
    assert m["mean"] == 5.0 and m["variance"] == 0.0
    assert math.isnan(m["skewness"]) and math.isnan(m["kurtosis"])


def test_ratings_to_shares():
    assert list(counts_from_ratings([5, 5, 4, 1])) == [1, 0, 0, 1, 2]
    assert shares_from_ratings([5, 5, 4, 1]) == pytest.approx([0.25, 0, 0, 0.25, 0.5])


def test_bad_input_rejected():
    with pytest.raises(ValueError):
        mean_and_variance([0.5, 0.5])
    with pytest.raises(ValueError):
        mean_and_variance([0.5, 0.5, 0.5, 0, 0])
    with pytest.raises(ValueError):
        counts_from_ratings([5, 7])
    with pytest.raises(ValueError):
        counts_from_ratings([4.5])
    with pytest.raises(ValueError):
        shares_from_ratings([])
