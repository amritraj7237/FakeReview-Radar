"""The four warning signals (docs/TRUST_SCORE.md section 2).

Each signal turns one kind of evidence into a strength s between 0 (nothing
unusual) and 1 (as strong as it gets), or None when it can't be measured.

Normalisation rule used for every signal: s = 0 up to the level that real
products commonly reach, then rises in a straight line to 1 at a level that is
clearly abnormal. The "starts at" points come from the real Amazon Electronics
sample (6,316 products with >= 20 reviews), NOT from the synthetic test data,
so the signals aren't tuned to the generator that we evaluate them on.

    signal       measures                                         starts at     full at
    bsi          two peaks with an empty middle                   (already 0-1)
    inflation    5-star share above normal and a thin 4-star bar  p5 = 0.75     p5 = 0.95
    unverified   share of unverified reviews (+ rating gap)       u  = 0.15     u  = 0.55
    burst        reviews packed into one 7- or 30-day window      0.15 / 0.20   + 0.20
"""

import numpy as np

from analysis.radar.bsi import PRIOR, bsi_from_shares, shrink_shares
from analysis.radar.cleaning import TOO_SMALL

# 5-star inflation
INFLATION_START, INFLATION_FULL = 0.75, 0.95
NORMAL_4_TO_5 = PRIOR[3] / PRIOR[4]          # 0.17 / 0.64 = 0.27 in a typical product

# unverified reviews
UNVERIFIED_START, UNVERIFIED_FULL = 0.15, 0.55
GAP_FULL = 1.0                               # a 1-star gap between groups counts fully
MIN_KNOWN = 5                                # verified + unverified reviews needed
MIN_GROUP_FOR_GAP = 3                        # reviews needed in each group for the gap

# date burst: (window in days, excess share where s starts)
BURST_WINDOWS = ((7, 0.15), (30, 0.20))
BURST_RAMP = 0.20                            # s reaches 1 this far above the start
MIN_DATED = 10                               # dated reviews needed


def ramp(x, start, full):
    """0 below start, 1 above full, a straight line in between."""
    return float(np.clip((x - start) / (full - start), 0.0, 1.0))


def bsi_signal(counts):
    """BSI after shrinkage. Needs at least 5 valid ratings."""
    counts = np.asarray(counts, dtype=float)
    if counts.sum() < TOO_SMALL:
        return None, {}
    p = shrink_shares(counts)
    value = bsi_from_shares(p)
    return value, {"p1": p[0], "p5": p[4], "middle": float(np.mean(p[1:4]))}


def inflation_signal(counts):
    """5-star share well above normal AND a 4-star bar thinner than normal.

    Real happy customers give a fair number of 4-star reviews too; bought reviews
    are almost all 5-star, so they push the 5-star bar up and the 4:5 ratio down.
    """
    counts = np.asarray(counts, dtype=float)
    if counts.sum() < TOO_SMALL:
        return None, {}
    p = shrink_shares(counts)
    excess = ramp(p[4], INFLATION_START, INFLATION_FULL)
    ratio = p[3] / p[4] if p[4] > 0 else 1.0
    thin_4 = ramp(-ratio, -NORMAL_4_TO_5, 0.0)   # 0 at the normal ratio, 1 when 4-star is empty
    return excess * thin_4, {"p5": p[4], "p4": p[3], "ratio_4_to_5": ratio}


def unverified_signal(ratings, verified):
    """Share of unverified reviews above normal, stronger when the groups rate differently.

    "unknown" reviews are left out of both groups, never counted as unverified.
    s = share_part x (0.5 + 0.5 x gap_part): a high unverified share alone gives at
    most 0.5; a rating gap between unverified and verified buyers adds the rest.
    """
    ratings = np.asarray(ratings, dtype=float)
    verified = np.asarray(verified, dtype=object)
    is_v, is_u = verified == "verified", verified == "unverified"
    known = int(is_v.sum() + is_u.sum())
    if known < MIN_KNOWN:
        return None, {}
    share = is_u.sum() / known
    share_part = ramp(share, UNVERIFIED_START, UNVERIFIED_FULL)
    rated_v = ratings[is_v & ~np.isnan(ratings)]
    rated_u = ratings[is_u & ~np.isnan(ratings)]
    gap = np.nan
    gap_part = 0.0
    if len(rated_v) >= MIN_GROUP_FOR_GAP and len(rated_u) >= MIN_GROUP_FOR_GAP:
        gap = float(rated_u.mean() - rated_v.mean())
        gap_part = ramp(abs(gap), 0.0, GAP_FULL)
    return share_part * (0.5 + 0.5 * gap_part), {"share": share, "gap": gap, "known": known}


def burst_signal(dates):
    """Busiest 7-day and 30-day windows compared with an even spread of the same reviews.

    excess_w = (reviews in the busiest w-day window - reviews expected in w days
    if spread evenly over the product's active period) / all dated reviews.
    """
    days = np.sort(np.asarray(dates, dtype="datetime64[D]").astype("int64"))
    n = len(days)
    if n < MIN_DATED:
        return None, {}
    span = days[-1] - days[0] + 1
    best, detail = 0.0, {}
    for window, start in BURST_WINDOWS:
        in_window = np.searchsorted(days, days + window, side="left") - np.arange(n)
        i = int(np.argmax(in_window))
        expected = n * window / max(span, window)
        excess = (in_window[i] - expected) / n
        s = ramp(excess, start, start + BURST_RAMP)
        detail[f"excess_{window}d"] = excess
        if s >= best and in_window[i] > 0:
            best = s
            detail.update(window=window, count=int(in_window[i]), start_day=int(days[i]))
    detail["n_dated"] = n
    return best, detail
