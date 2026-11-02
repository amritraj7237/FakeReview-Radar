"""Generate a labelled synthetic review dataset for FakeReview Radar.

Real Amazon data has no "fake / real" labels, so to measure how accurate the
detector is we need data where we already know the answer. This script builds
products following five patterns (PRD section 6):

    genuine_j          not manipulated  J-shaped ratings, ~90 % verified, dates over a year
    genuine_divisive   not manipulated  naturally split ratings, mostly verified, spread dates
    bimodal_attack     manipulated      genuine + injected block of only 1/5 stars, mostly unverified, ~10 days
    positive_stuffing  manipulated      genuine + injected block of almost all 5 stars, many unverified
    burst_campaign     manipulated      genuine + injected 5-star-heavy block in ~4 days, mostly verified

Usage:
    python analysis/generate_synthetic.py                 # seed 42 -> data/reviews_synthetic.csv
    python analysis/generate_synthetic.py --seed 7 --out data/reviews_synthetic_seed7.csv
    python analysis/generate_synthetic.py --plot          # also save one histogram per pattern to outputs/
"""

import argparse
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

STARS = np.array([1, 2, 3, 4, 5])

# How strongly each product's genuine shares stick to the template. Higher means
# less product-to-product variation (Dirichlet concentration).
CONCENTRATION = 60

# Genuine part of every product: rating shares, probability a review is verified.
GENUINE = {
    "genuine_j":        {"shares": [0.08, 0.04, 0.07, 0.17, 0.64], "verified": 0.90},
    "genuine_divisive": {"shares": [0.28, 0.08, 0.08, 0.14, 0.42], "verified": 0.85},
}

# Injected block added on top of a genuine J-shaped product.
#   size     = injected reviews as a fraction of the genuine reviews (min, max)
#   window   = number of days the injected block is squeezed into
INJECTED = {
    "bimodal_attack": {
        "shares": [0.45, 0.00, 0.00, 0.00, 0.55],
        "verified": 0.20,
        "window": 10,
        "size": (0.4, 0.8),
    },
    "positive_stuffing": {
        "shares": [0.00, 0.00, 0.01, 0.04, 0.95],
        "verified": 0.35,
        "window": 30,
        "size": (0.4, 0.8),
    },
    "burst_campaign": {
        "shares": [0.01, 0.01, 0.03, 0.15, 0.80],
        "verified": 0.85,
        "window": 4,
        "size": (0.4, 0.8),
    },
}

PATTERNS = list(GENUINE) + list(INJECTED)

COLUMNS = [
    "product_id", "review_id", "rating", "review_date", "verified_purchase",
    "source", "pattern", "is_manipulated_product", "is_injected",
]


def make_reviews(rng, n, shares, verified_prob, dates):
    """Return n review dicts with ratings drawn from `shares` and the given dates."""
    ratings = rng.choice(STARS, size=n, p=shares)
    verified = rng.random(n) < verified_prob
    return [
        {"rating": int(r), "review_date": d, "verified_purchase": bool(v)}
        for r, d, v in zip(ratings, dates, verified)
    ]


def make_product(pattern, n_reviews, rng, product_id, end_date):
    """Build every review row for one product of the given pattern."""
    # 1. Genuine reviews. Manipulated products start from a genuine J-shape.
    base = GENUINE.get(pattern, GENUINE["genuine_j"])
    shares = rng.dirichlet(CONCENTRATION * np.array(base["shares"]))
    days_back = rng.integers(0, 366, size=n_reviews)
    dates = [end_date - timedelta(days=int(d)) for d in days_back]
    reviews = make_reviews(rng, n_reviews, shares, base["verified"], dates)
    for r in reviews:
        r["is_injected"] = False

    # 2. Injected block, all inside a short date window.
    if pattern in INJECTED:
        spec = INJECTED[pattern]
        n_inj = max(1, round(n_reviews * rng.uniform(*spec["size"])))
        window_start = end_date - timedelta(days=int(rng.integers(spec["window"], 366)))
        offsets = rng.integers(0, spec["window"], size=n_inj)
        inj_dates = [window_start + timedelta(days=int(o)) for o in offsets]
        injected = make_reviews(rng, n_inj, spec["shares"], spec["verified"], inj_dates)
        for r in injected:
            r["is_injected"] = True
        reviews += injected

    reviews.sort(key=lambda r: r["review_date"])
    for i, r in enumerate(reviews, start=1):
        r["product_id"] = product_id
        r["review_id"] = f"{product_id}-R{i:04d}"
        r["source"] = "synthetic"
        r["pattern"] = pattern
        r["is_manipulated_product"] = pattern in INJECTED
    return reviews


def generate(seed=42, products_per_pattern=40, min_reviews=30, max_reviews=300,
             end_date=date(2025, 12, 31)):
    """Generate the whole dataset as a DataFrame. Same seed -> same data."""
    rng = np.random.default_rng(seed)
    rows = []
    product_no = 0
    for pattern in PATTERNS:
        for _ in range(products_per_pattern):
            product_no += 1
            n = int(rng.integers(min_reviews, max_reviews + 1))
            rows += make_product(pattern, n, rng, f"SYN{product_no:04d}", end_date)
    df = pd.DataFrame(rows, columns=COLUMNS)
    df["review_date"] = pd.to_datetime(df["review_date"]).dt.strftime("%Y-%m-%d")
    return df


def summarize(df):
    """Self-check: average rating, % verified and % injected per pattern."""
    summary = df.groupby("pattern", sort=False).agg(
        products=("product_id", "nunique"),
        reviews=("review_id", "count"),
        avg_rating=("rating", "mean"),
        pct_verified=("verified_purchase", "mean"),
        pct_injected=("is_injected", "mean"),
    )
    summary["pct_verified"] *= 100
    summary["pct_injected"] *= 100
    return summary.round(2)


def plot_examples(df, out_path):
    """Save the star histogram of the first product of each pattern."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, len(PATTERNS), figsize=(3.2 * len(PATTERNS), 3), sharey=False)
    for ax, pattern in zip(axes, PATTERNS):
        pid = df.loc[df["pattern"] == pattern, "product_id"].iloc[0]
        ratings = df.loc[df["product_id"] == pid, "rating"]
        counts = ratings.value_counts().reindex(STARS, fill_value=0)
        ax.bar(STARS, counts / counts.sum(), color="#4472c4")
        ax.set_title(f"{pattern}\n{pid} (n={len(ratings)})", fontsize=9)
        ax.set_xticks(STARS)
        ax.set_xlabel("stars")
    axes[0].set_ylabel("share of reviews")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=42, help="random seed (default 42)")
    parser.add_argument("--products-per-pattern", type=int, default=40)
    parser.add_argument("--out", default="data/reviews_synthetic.csv")
    parser.add_argument("--plot", action="store_true",
                        help="save example histograms to outputs/synthetic_patterns_seed<seed>.png")
    args = parser.parse_args()

    df = generate(seed=args.seed, products_per_pattern=args.products_per_pattern)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"Wrote {len(df)} reviews for {df['product_id'].nunique()} products to {out}")
    print(summarize(df).to_string())

    if args.plot:
        plot_path = Path("outputs") / f"synthetic_patterns_seed{args.seed}.png"
        plot_path.parent.mkdir(exist_ok=True)
        plot_examples(df, plot_path)
        print(f"Saved example histograms to {plot_path}")


if __name__ == "__main__":
    main()
