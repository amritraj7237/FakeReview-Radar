"""Load and inspect the first lines of Amazon Reviews 2023, Electronics (Task 9).

Prints the numbers that go into docs/WEEK1_FINDINGS.md and saves two charts:

    outputs/electronics_sample_ratings.png      rating histogram of the real sample
    outputs/real_vs_synthetic_genuine_j.png     real shares vs synthetic genuine_j shares

Get the sample first (about 3.5 MB, git-ignored):

    mkdir -p data/raw
    curl -sL https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/review_categories/Electronics.jsonl \
        | head -n 5000 > data/raw/electronics_sample.jsonl

Usage:
    python analysis/inspect_sample.py
    python analysis/inspect_sample.py --sample data/raw/other.jsonl --nrows 2000
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # so `analysis.radar` imports work
from analysis.radar.metrics import STARS, rating_metrics  # noqa: E402

BLUE, ORANGE = "#2a78d6", "#eb6834"   # categorical slots 1 and 2
INK, MUTED, GRID = "#1f1f1e", "#6b6a63", "#e4e3dd"


def section(title):
    print(f"\n## {title}")


def load_sample(path, nrows):
    """Read JSON Lines with no type guessing, then convert each field on purpose."""
    # dtype=False stops pandas guessing types; otherwise it silently turns any
    # column called "timestamp" into a date and we never see the raw value.
    df = pd.read_json(path, lines=True, nrows=nrows, dtype=False)
    df["review_date"] = pd.to_datetime(df["timestamp"], unit="ms", errors="coerce")
    return df


def shares(ratings):
    counts = ratings.value_counts().reindex(STARS, fill_value=0)
    return counts / counts.sum()


def inspect(df):
    section("Shape and types")
    print(df.shape)
    print(df.dtypes.to_string())

    section("First rows")
    head = df.drop(columns=["images"]).head().copy()
    for col in ["title", "text", "user_id"]:
        head[col] = head[col].str.slice(0, 24) + "…"
    print(head.to_string())

    section("Missing values per column (NaN / None)")
    print(df.isna().sum().to_string())

    section("Empty strings")
    for col in ["title", "text", "user_id", "parent_asin"]:
        print(f"{col}: {(df[col].astype(str).str.strip() == '').sum()}")

    section("Rating counts")
    counts = df["rating"].value_counts(dropna=False).sort_index()
    print(pd.DataFrame({"count": counts, "pct": (counts / len(df) * 100).round(2)}).to_string())
    valid = df["rating"].isin(STARS)
    print(f"ratings outside 1-5 or missing: {(~valid).sum()}")
    m = rating_metrics(shares(df.loc[valid, "rating"]).to_numpy())
    print("whole-sample metrics: " + ", ".join(f"{k} = {v:.3f}" for k, v in m.items()))

    section("Verified purchase")
    print(df["verified_purchase"].value_counts(dropna=False).to_string())
    print(f"% verified: {df['verified_purchase'].eq(True).mean() * 100:.1f}")
    by_group = df[valid].groupby("verified_purchase")["rating"].agg(["count", "mean"])
    print(by_group.round(3).to_string())

    section("Date range")
    print(f"min: {df['review_date'].min()}   max: {df['review_date'].max()}")
    print(f"unparseable timestamps: {df['review_date'].isna().sum()}")
    print("reviews per year:")
    print(df["review_date"].dt.year.value_counts().sort_index().to_string())

    section("Products")
    per_product = df.groupby("parent_asin").size().sort_values(ascending=False)
    print(f"distinct parent_asin: {per_product.size}   distinct asin: {df['asin'].nunique()}")
    print(f"products with < 5 reviews: {(per_product < 5).sum()}   "
          f"< 20 reviews: {(per_product < 20).sum()}   >= 20: {(per_product >= 20).sum()}")
    print("top 10 products by review count:")
    print(per_product.head(10).to_string())

    section("Cleaning-rule checks (docs/CLEANING_RULES.md)")
    key = ["user_id", "parent_asin", "timestamp"]
    print(f"R3 duplicate rows on user_id + parent_asin + timestamp: {df.duplicated(key).sum()}")
    print(f"R3 duplicate rows on user_id + parent_asin + text + date: "
          f"{df.assign(d=df['review_date'].dt.date).duplicated(['user_id', 'parent_asin', 'text', 'd']).sum()}")
    print(f"R5 missing verified_purchase: {df['verified_purchase'].isna().sum()}")
    print(f"R6 missing or empty text: {(df['text'].isna() | (df['text'].astype(str).str.strip() == '')).sum()}")
    print(f"helpful_vote missing: {df['helpful_vote'].isna().sum()}   "
          f"zero: {(df['helpful_vote'] == 0).sum()}")
    users = df.groupby("user_id").size()
    print(f"distinct users: {users.size}   users with > 1 review in sample: {(users > 1).sum()}")


def style(ax):
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    for side in ["left", "bottom"]:
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, length=0)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_xticks(STARS, [f"{s}★" for s in STARS])


def plot_histogram(df, out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ratings = df.loc[df["rating"].isin(STARS), "rating"]
    counts = ratings.value_counts().reindex(STARS, fill_value=0)
    fig, ax = plt.subplots(figsize=(6.4, 4))
    bars = ax.bar(STARS, counts, width=0.7, color=BLUE)
    for bar, c in zip(bars, counts):
        ax.annotate(f"{c:,}\n{c / counts.sum():.0%}", (bar.get_x() + bar.get_width() / 2, c),
                    xytext=(0, 3), textcoords="offset points", ha="center", va="bottom",
                    fontsize=8, color=INK)
    style(ax)
    ax.set_ylim(0, counts.max() * 1.18)
    ax.set_xlabel("star rating", color=MUTED)
    ax.set_ylabel("number of reviews", color=MUTED)
    ax.set_title(f"Amazon Electronics, first {len(ratings):,} reviews: a J-shape",
                 loc="left", fontsize=11, color=INK)
    fig.text(0.01, 0.01, "Source: Amazon Reviews 2023 (McAuley Lab), Electronics.jsonl, "
             "first lines of file; not a random sample.", fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def plot_comparison(real, synth, n_real, n_synth, out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    w = 0.36
    fig, ax = plt.subplots(figsize=(6.4, 4))
    ax.bar(STARS - w / 2 - 0.01, real, width=w, color=BLUE, label=f"real sample (n={n_real:,})")
    ax.bar(STARS + w / 2 + 0.01, synth, width=w, color=ORANGE,
           label=f"synthetic genuine_j (n={n_synth:,})")
    for s, r, y in zip(STARS, real, synth):
        ax.annotate(f"{r:.0%}", (s - w / 2, r), xytext=(0, 2), textcoords="offset points",
                    ha="center", fontsize=7, color=INK)
        ax.annotate(f"{y:.0%}", (s + w / 2, y), xytext=(0, 2), textcoords="offset points",
                    ha="center", fontsize=7, color=INK)
    style(ax)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("star rating", color=MUTED)
    ax.set_ylabel("share of reviews", color=MUTED)
    ax.set_title("Real Electronics sample vs synthetic genuine_j", loc="left", fontsize=11, color=INK)
    ax.legend(frameon=False, fontsize=8, labelcolor=INK)
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def compare_synthetic(df, synth_path, out_path):
    section("Real vs synthetic genuine_j")
    synth = pd.read_csv(synth_path)
    genuine = synth.loc[synth["pattern"] == "genuine_j", "rating"]
    real = df.loc[df["rating"].isin(STARS), "rating"]
    table = pd.DataFrame({"real": shares(real), "synthetic_genuine_j": shares(genuine),
                          "prior_pi": [0.08, 0.04, 0.07, 0.17, 0.64]})
    table["real_minus_synth"] = table["real"] - table["synthetic_genuine_j"]
    print((table * 100).round(1).to_string())
    for name, s in [("real", shares(real)), ("synthetic genuine_j", shares(genuine))]:
        m = rating_metrics(s.to_numpy())
        print(f"{name}: " + ", ".join(f"{k} = {v:.3f}" for k, v in m.items()))
    print(f"verified: real {df['verified_purchase'].eq(True).mean():.1%}, "
          f"synthetic genuine_j {synth.loc[synth['pattern'] == 'genuine_j', 'verified_purchase'].mean():.1%}")
    plot_comparison(table["real"], table["synthetic_genuine_j"], len(real), len(genuine), out_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sample", default="data/raw/electronics_sample.jsonl")
    parser.add_argument("--nrows", type=int, default=5000)
    parser.add_argument("--synthetic", default="data/reviews_synthetic.csv")
    args = parser.parse_args()

    df = load_sample(args.sample, args.nrows)
    inspect(df)

    Path("outputs").mkdir(exist_ok=True)
    plot_histogram(df, "outputs/electronics_sample_ratings.png")
    if Path(args.synthetic).exists():
        compare_synthetic(df, args.synthetic, "outputs/real_vs_synthetic_genuine_j.png")
    print("\nSaved outputs/electronics_sample_ratings.png and outputs/real_vs_synthetic_genuine_j.png")


if __name__ == "__main__":
    main()
