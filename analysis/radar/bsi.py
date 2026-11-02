"""Bimodal Suspicion Index (BSI), PRD section 9.

    BSI = S x D
    S   = variance / 4                                   spread, 0 to 1
    D   = max(0, 1 - mean(p2, p3, p4) / min(p1, p5))     valley depth, 0 to 1

Shares are first shrunk toward a typical product so that tiny products are not
flagged by luck:

    p~_s = (n * p_s + k * pi_s) / (n + k),   pi = (0.08, 0.04, 0.07, 0.17, 0.64),  k = 10
"""

import numpy as np

STARS = np.array([1, 2, 3, 4, 5])
PRIOR = np.array([0.08, 0.04, 0.07, 0.17, 0.64])  # typical J-shaped product
K = 10                                             # prior strength, in "pseudo-reviews"
MAX_VARIANCE = 4.0                                 # half 1-star, half 5-star


# TEMPORARY: Chirag's Task 6 provides mean_and_variance(p) in analysis/radar/metrics.py.
# On Day 6 delete this function and replace it with:
#     from analysis.radar.metrics import mean_and_variance
def mean_and_variance(p):
    """Mean and variance of a 1-5 star rating, given 5 shares that sum to 1."""
    p = np.asarray(p, dtype=float)
    mean = float(np.sum(STARS * p))
    variance = float(np.sum(p * (STARS - mean) ** 2))
    return mean, variance


def shrink_shares(counts, prior=PRIOR, k=K):
    """Turn 5 star counts into shares pulled toward `prior` by k pseudo-reviews."""
    counts = np.asarray(counts, dtype=float)
    if counts.shape != (5,):
        raise ValueError("counts must have exactly 5 values (1-star to 5-star)")
    if (counts < 0).any():
        raise ValueError("counts cannot be negative")
    n = counts.sum()
    return (counts + k * np.asarray(prior)) / (n + k)


def spread(p):
    """S: variance scaled to 0..1 by the largest possible variance (4)."""
    _, variance = mean_and_variance(p)
    return variance / MAX_VARIANCE


def valley_depth(p):
    """D: how far the middle (2-4 stars) sinks below the lower of the two ends.

    If either end is empty (min(p1, p5) == 0) there are not two peaks, so there
    is no valley between them: D = 0.
    """
    lower_peak = min(p[0], p[4])
    if lower_peak <= 0:
        return 0.0
    middle = np.mean(p[1:4])
    return max(0.0, 1.0 - middle / lower_peak)


def bsi_from_shares(p):
    """BSI of 5 shares that sum to 1 (no shrinkage)."""
    p = np.asarray(p, dtype=float)
    if p.shape != (5,) or not np.isclose(p.sum(), 1.0):
        raise ValueError("p must be 5 shares that sum to 1")
    return spread(p) * valley_depth(p)


def bsi(counts, k=K):
    """BSI of a product from its 5 star counts, after shrinkage (k=0 turns it off)."""
    return bsi_from_shares(shrink_shares(counts, k=k))


if __name__ == "__main__":
    big = 100_000  # large n so shrinkage barely matters
    checks = {
        "A  J-shape  8/4/7/17/64": ([0.08, 0.04, 0.07, 0.17, 0.64], 0.00),
        "divisive   28/8/8/14/42": ([0.28, 0.08, 0.08, 0.14, 0.42], 0.47),
        "attack     38/2/2/4/54":  ([0.38, 0.02, 0.02, 0.04, 0.54], 0.84),
    }
    for name, (shares, expected) in checks.items():
        value = bsi(np.array(shares) * big)
        print(f"{name}: BSI = {value:.3f}  (expected ~{expected:.2f})")

    six = [1, 0, 0, 0, 5]  # five 5-star reviews and one 1-star
    print(f"6-review product: raw BSI = {bsi(six, k=0):.3f}, shrunk BSI = {bsi(six):.3f}")
