"""Trust score: combine the warning signals with noisy-OR (docs/TRUST_SCORE.md).

    R     = 1 - (1 - c1 s1)(1 - c2 s2)...(1 - ck sk)      only measured signals
    Trust = round_half_up(1 + 99 x (1 - R))

The score is a heuristic review-quality indicator, not a probability that the
reviews are genuine. Higher = fewer warning signs.
"""

import math

RELIABILITY = {"bsi": 0.50, "inflation": 0.70, "unverified": 0.60, "burst": 0.70}

BANDS = ((66, "looks genuine"), (45, "mixed signals"), (1, "suspicious"))
FLAG_BELOW = 66


def round_half_up(x):
    """Python's round() sends 50.5 to 50 (banker's rounding); we want 51."""
    return math.floor(x + 0.5)


def combine(signals, reliability=RELIABILITY):
    """signals: {name: s or None}. None = not measured, skipped (same as s = 0)."""
    keep = 1.0
    for name, s in signals.items():
        if s is not None:
            keep *= 1.0 - reliability[name] * s
    return 1.0 - keep


def trust_score(risk):
    return round_half_up(1 + 99 * (1 - risk))


def band(score):
    for lower, name in BANDS:
        if score >= lower:
            return name
    return BANDS[-1][1]


def score(signals, reliability=RELIABILITY):
    """Everything the dashboard needs for one product."""
    risk = combine(signals, reliability)
    value = trust_score(risk)
    contributions = {name: reliability[name] * s for name, s in signals.items() if s is not None}
    return {
        "risk": risk,
        "trust_score": value,
        "band": band(value),
        "flag": value < FLAG_BELOW,
        "contributions": contributions,
        "not_measured": [name for name, s in signals.items() if s is None],
    }
