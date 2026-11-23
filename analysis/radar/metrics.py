"""Rating metrics from the five star shares p1..p5 (PRD section 5, Task 6).

Every metric is computed from the shares alone, no individual reviews needed:

    mean      mu   = sum s * p_s                       (s = 1..5)
    variance  var  = sum (s - mu)^2 * p_s
    skewness       = sum (s - mu)^3 * p_s / sigma^3
    kurtosis       = sum (s - mu)^4 * p_s / sigma^4 - 3   ("excess" kurtosis)

These are *population* moments (divide by n, not n - 1), which is what
scipy.stats.skew / scipy.stats.kurtosis return with their default bias=True.

If every review has the same star (sigma = 0) skewness and kurtosis divide by
zero, so they are "not defined" and we return NaN. See docs/METRICS.md.
"""

import numpy as np

STARS = np.array([1, 2, 3, 4, 5])


def _check_shares(p):
    """Return p as a float array, or raise if it is not 5 shares that sum to 1."""
    p = np.asarray(p, dtype=float)
    if p.shape != (5,):
        raise ValueError("p must have exactly 5 values (1-star to 5-star)")
    if (p < 0).any() or not np.isclose(p.sum(), 1.0):
        raise ValueError("p must be 5 non-negative shares that sum to 1")
    return p


def counts_from_ratings(ratings):
    """Count how many 1-, 2-, 3-, 4- and 5-star ratings there are.

    Ratings must already be clean (whole numbers 1 to 5); cleaning is a separate
    step with its own log, so anything else here is a bug and raises.
    """
    ratings = np.asarray(ratings, dtype=float)
    if not np.isin(ratings, STARS).all():
        raise ValueError("ratings must be whole numbers from 1 to 5 (clean them first)")
    return np.array([(ratings == s).sum() for s in STARS])


def shares_from_ratings(ratings):
    """Turn a list of ratings into the 5 shares p1..p5 (they sum to 1)."""
    counts = counts_from_ratings(ratings)
    if counts.sum() == 0:
        raise ValueError("need at least one rating to compute shares")
    return counts / counts.sum()


def mean_and_variance(p):
    """Mean and variance of a 1-5 star rating, given 5 shares that sum to 1."""
    p = _check_shares(p)
    mean = float(np.sum(STARS * p))
    variance = float(np.sum(p * (STARS - mean) ** 2))
    return mean, variance


def _standardised_moment(p, power):
    """sum (s - mu)^power * p_s / sigma^power, or NaN when sigma = 0."""
    mean, variance = mean_and_variance(p)
    if np.isclose(variance, 0.0):
        return float("nan")
    p = np.asarray(p, dtype=float)
    return float(np.sum(p * (STARS - mean) ** power) / variance ** (power / 2))


def skewness(p):
    """Skewness: negative = long tail toward 1 star (a J-shape), 0 = symmetric."""
    return _standardised_moment(p, 3)


def kurtosis(p):
    """Excess kurtosis: below 0 = weight pushed to the two ends or flat, above 0 = one sharp peak."""
    value = _standardised_moment(p, 4)
    return value - 3 if not np.isnan(value) else value


def rating_metrics(p):
    """All four metrics for one product as a dict."""
    mean, variance = mean_and_variance(p)
    return {
        "mean": mean,
        "variance": variance,
        "skewness": skewness(p),
        "kurtosis": kurtosis(p),
    }


if __name__ == "__main__":
    charts = {
        "A  J-shape  8/4/7/17/64":    [0.08, 0.04, 0.07, 0.17, 0.64],
        "B  attack   38/2/2/4/54":    [0.38, 0.02, 0.02, 0.04, 0.54],
        "C  flat     20/20/20/20/20": [0.20, 0.20, 0.20, 0.20, 0.20],
        "divisive    28/8/8/14/42":   [0.28, 0.08, 0.08, 0.14, 0.42],
        "all 5-star  0/0/0/0/100":    [0.00, 0.00, 0.00, 0.00, 1.00],
    }
    for name, shares in charts.items():
        m = rating_metrics(shares)
        print(f"{name}: mean = {m['mean']:.4f}  var = {m['variance']:.4f}  "
              f"skew = {m['skewness']:.4f}  kurt = {m['kurtosis']:.4f}")
