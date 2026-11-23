"""Product-level table: one row per product (DATA_DICTIONARY.md section 4).

    reviews, log = clean(raw)
    products = build_product_table(reviews)

Each row has the star counts and shares, rating metrics, verification counts,
BSI, the four signal strengths, the trust score, its band and flag, and up to
three plain-language reasons.
"""

import numpy as np
import pandas as pd

from analysis.radar import signals as sig
from analysis.radar.cleaning import sample_status
from analysis.radar.metrics import STARS, rating_metrics
from analysis.radar.trust import score

SIGNALS = ["bsi", "inflation", "unverified", "burst"]
MIN_CONTRIBUTION = 0.10     # a signal must add at least this much (c x s) to be listed as a reason


def _reason(name, s, detail):
    if name == "bsi":
        return (f"Ratings split into two camps: {detail['p1']:.0%} 1★ and {detail['p5']:.0%} 5★ "
                f"with few in between (BSI {s:.2f}).")
    if name == "inflation":
        return (f"{detail['p5']:.0%} of ratings are 5★ but only {detail['p4']:.0%} are 4★, "
                f"more one-sided than typical products.")
    if name == "unverified":
        text = f"{detail['share']:.0%} of reviews are not verified purchases (typical: under 15%)"
        gap = detail.get("gap")
        if gap is not None and not np.isnan(gap) and abs(gap) >= 0.3:
            text += (f"; unverified reviewers rate {abs(gap):.1f}★ "
                     f"{'lower' if gap < 0 else 'higher'} on average")
        return text + "."
    if name == "burst":
        start = pd.Timestamp(detail["start_day"], unit="D").date()
        return (f"{detail['count']} of {detail['n_dated']} dated reviews "
                f"({detail['count'] / detail['n_dated']:.0%}) arrived within "
                f"{detail['window']} days from {start}.")
    raise ValueError(name)


def low_sample_warning(status, n_rated):
    if status == "too_small":
        return f"Only {n_rated} valid rating(s): not enough data to score this product."
    if status == "small":
        return f"Only {n_rated} valid ratings: the score is uncertain, treat it with caution."
    return ""


def score_product(ratings, verified, dates):
    """Signals, trust score and reasons for one product's reviews."""
    ratings = np.asarray(ratings, dtype=float)
    rated = ratings[~np.isnan(ratings)].astype(int)
    counts = np.bincount(rated, minlength=6)[1:] if len(rated) else np.zeros(5, dtype=int)
    n_rated = int(counts.sum())
    status = sample_status(n_rated)

    found = {
        "bsi": sig.bsi_signal(counts),
        "inflation": sig.inflation_signal(counts),
        "unverified": sig.unverified_signal(ratings, verified),
        "burst": sig.burst_signal(dates),
    }
    strengths = {name: value for name, (value, _) in found.items()}
    result = score(strengths)

    reasons = sorted(((c, name) for name, c in result["contributions"].items()
                      if c >= MIN_CONTRIBUTION), reverse=True)[:3]
    row = {
        "counts": counts,
        "n_rated": n_rated,
        "sample_status": status,
        "s": strengths,
        "risk": result["risk"],
        "trust_score": result["trust_score"],
        "band": result["band"],
        "flag": result["flag"],
        "signals_not_measured": ";".join(result["not_measured"]),
        "reasons": [_reason(name, strengths[name], found[name][1]) for _, name in reasons],
        "warning": low_sample_warning(status, n_rated),
    }
    if status == "too_small":
        # every rating signal is "not measured", which would give a meaningless 100
        row.update(trust_score=np.nan, band="insufficient data", flag=False)
    return row


def build_product_table(reviews):
    rows = []
    for (product_id, source), g in reviews[reviews["product_id"].notna()].groupby(
            ["product_id", "source"], sort=False):
        ratings = g["rating"].astype("Float64").to_numpy(dtype=float, na_value=np.nan)
        verified = g["verified_purchase"].astype(str).to_numpy()
        dates = g["review_date"].dropna().to_numpy()
        res = score_product(ratings, verified, dates)
        counts, n_rated = res["counts"], res["n_rated"]
        shares = counts / n_rated if n_rated else np.full(5, np.nan)
        metrics = rating_metrics(shares) if n_rated else dict.fromkeys(
            ["mean", "variance", "skewness", "kurtosis"], np.nan)
        n_v, n_u = int((verified == "verified").sum()), int((verified == "unverified").sum())
        row = {
            "product_id": product_id,
            "source": source,
            "n_reviews": len(g),
            "n_rated": n_rated,
            **{f"count_{s}": int(c) for s, c in zip(STARS, counts)},
            **{f"p{s}": p for s, p in zip(STARS, shares)},
            **metrics,
            "n_verified": n_v,
            "n_unverified": n_u,
            "n_unknown": int((verified == "unknown").sum()),
            "pct_unverified": n_u / (n_v + n_u) if n_v + n_u else np.nan,
            "first_date": g["review_date"].min(),
            "last_date": g["review_date"].max(),
            "sample_status": res["sample_status"],
            "bsi": res["s"]["bsi"],
            "s_inflation": res["s"]["inflation"],
            "s_unverified": res["s"]["unverified"],
            "s_burst": res["s"]["burst"],
            "signals_not_measured": res["signals_not_measured"],
            "risk": res["risk"],
            "trust_score": res["trust_score"],
            "band": res["band"],
            "flag": res["flag"],
            "reason_1": "", "reason_2": "", "reason_3": "",
            "warning": res["warning"],
        }
        for i, text in enumerate(res["reasons"], start=1):
            row[f"reason_{i}"] = text
        if g["pattern"].notna().any():
            row["pattern"] = g["pattern"].iloc[0]
            row["is_manipulated_product"] = bool(g["is_manipulated_product"].iloc[0])
        rows.append(row)
    table = pd.DataFrame(rows)
    table["trust_score"] = table["trust_score"].astype("Int64")
    return table
