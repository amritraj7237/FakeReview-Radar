"""Clean, score and analyse the real Amazon Electronics sample (PRD section 10).

Needs data/raw/electronics_products.jsonl (run analysis/download_sample.py first).

Writes to outputs/real/:
    cleaning_log_real.csv          one row per cleaning rule
    products_real.csv              product table: metrics, BSI, signals, trust score, reasons
    flagged_products_real.csv      CSV export of flagged products (trust < 66)
    verified_comparison.csv        rating shape of verified / unverified / unknown reviews
    *.png                          charts used in docs/FINDINGS_REPORT.md

Usage:
    python analysis/analyze_real.py
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.radar import charts  # noqa: E402
from analysis.radar.cleaning import clean, load_amazon_jsonl  # noqa: E402
from analysis.radar.metrics import STARS, rating_metrics  # noqa: E402
from analysis.radar.products import build_product_table  # noqa: E402
from analysis.radar.trust import FLAG_BELOW  # noqa: E402

RAW = Path("data/raw/electronics_products.jsonl")
OUT = Path("outputs/real")


def group_shape(ratings):
    ratings = ratings.dropna().astype(int)
    counts = np.bincount(ratings, minlength=6)[1:]
    row = {"reviews": int(counts.sum())}
    if counts.sum() == 0:
        return row
    shares = counts / counts.sum()
    row.update({f"p{s}": p for s, p in zip(STARS, shares)})
    row.update(rating_metrics(shares))
    return row


def verified_comparison(reviews):
    rows = []
    for group in ["verified", "unverified", "unknown"]:
        rows.append({"group": group, **group_shape(reviews.loc[reviews["verified_purchase"] == group, "rating"])})
    return pd.DataFrame(rows)


def flagged_comparison(reviews, products):
    """Rating shape of all reviews in flagged vs not-flagged products (only 'ok' products)."""
    ok = products[products["sample_status"] == "ok"]
    rows = []
    for label, ids in [("flagged products", ok.loc[ok["flag"], "product_id"]),
                       ("not flagged", ok.loc[~ok["flag"], "product_id"])]:
        rows.append({"group": label, "products": len(ids),
                     **group_shape(reviews.loc[reviews["product_id"].isin(ids), "rating"])})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- charts

def plot_verified(table, path):
    fig, ax = charts.new_figure()
    w = 0.36
    shown = table[table["reviews"] > 0].reset_index(drop=True)
    colors = [charts.BLUE, charts.ORANGE, charts.AQUA]
    for k, row in shown.iterrows():
        shares = [row[f"p{s}"] for s in STARS]
        offset = (k - (len(shown) - 1) / 2) * (w + 0.02)
        ax.bar(STARS + offset, shares, width=w, color=colors[k],
               label=f"{row['group']} (n={int(row['reviews']):,}, mean {row['mean']:.2f})")
        for s, p in zip(STARS, shares):
            ax.annotate(f"{p:.0%}", (s + offset, p), xytext=(0, 2), textcoords="offset points",
                        ha="center", fontsize=7, color=charts.INK)
    ax.set_xticks(STARS, [f"{s}★" for s in STARS])
    ax.yaxis.set_major_formatter(__import__("matplotlib").ticker.PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("star rating")
    ax.set_ylabel("share of reviews in group")
    ax.legend(frameon=False, fontsize=8, labelcolor=charts.INK, loc="upper left")
    charts.style(ax)
    unknown = int(table.loc[table["group"] == "unknown", "reviews"].iloc[0])
    u = table.set_index("group")
    charts.finish(fig, ax, "Verified vs unverified reviews: real Electronics sample",
                  f"Observed. Unverified reviews are more extreme: {u.loc['unverified', 'p1']:.0%} 1★ "
                  f"vs {u.loc['verified', 'p1']:.0%} for verified. Unknown status: {unknown} reviews "
                  "(this source always records verification).", path)


def plot_volume(reviews, path):
    monthly = reviews.dropna(subset=["review_date"]).set_index("review_date").resample("MS").size()
    monthly = monthly["2005":]
    fig, ax = charts.new_figure(7.4, 4.0)
    ax.plot(monthly.index, monthly.values, color=charts.BLUE, linewidth=2)
    peak = monthly.idxmax()
    ax.annotate(f"peak {monthly.max():,} reviews\n{peak:%b %Y}", (peak, monthly.max()),
                xytext=(-80, -8), textcoords="offset points", fontsize=7.5, color=charts.INK,
                arrowprops={"arrowstyle": "-", "color": charts.MUTED, "linewidth": 0.8})
    ax.set_xlabel("month")
    ax.set_ylabel("reviews per month")
    charts.style(ax)
    charts.finish(fig, ax, "Review volume over time: real Electronics sample",
                  f"Observed. n = {monthly.sum():,} dated reviews of {reviews['product_id'].nunique():,} "
                  "products. Volume rises with Amazon's growth, so bursts must be judged per product.", path)


def plot_trust(products, path):
    ok = products[products["sample_status"] != "too_small"]
    fig, ax = charts.new_figure()
    bins = np.arange(0.5, 101.5, 5)
    counts, edges = np.histogram(ok["trust_score"].astype(float), bins=bins)
    for left, c in zip(edges[:-1], counts):
        mid = left + 2.5
        color = charts.GOOD if mid >= 66 else charts.WARNING if mid >= 45 else charts.CRITICAL
        ax.bar(mid, c, width=4.6, color=color)
    ax.set_yscale("log")
    ax.set_xlabel("trust score (heuristic, 1-100)")
    ax.set_ylabel("products (log scale)")
    for x, label in [(83, "66-100 looks genuine"), (55, "45-65 mixed"), (22, "1-44 suspicious")]:
        ax.text(x, ax.get_ylim()[1] * 0.6, label, ha="center", fontsize=7.5, color=charts.MUTED)
    flagged = ok["flag"].mean()
    charts.style(ax)
    charts.finish(fig, ax, "Trust scores of real Electronics products",
                  f"Heuristic flag, not proof. n = {len(ok):,} products with >= 5 ratings; "
                  f"{flagged:.1%} score below {FLAG_BELOW} and are flagged for a closer look.", path)


def plot_bsi_vs_mean(products, path):
    ok = products[products["sample_status"] == "ok"]
    fig, ax = charts.new_figure()
    for flagged, color, label in [(False, charts.BLUE, "not flagged"), (True, charts.ORANGE, "flagged (trust < 66)")]:
        rows = ok[ok["flag"] == flagged]
        ax.scatter(rows["mean"], rows["bsi"], s=10 if not flagged else 16, color=color, alpha=0.55 if not flagged else 0.9,
                   edgecolor=charts.SURFACE, linewidth=0.4, label=f"{label} ({len(rows):,})", zorder=3 if flagged else 2)
    ax.set_xlabel("average rating (stars)")
    ax.set_ylabel("BSI (0 = no valley, 1 = perfect U)")
    ax.legend(frameon=False, fontsize=8, labelcolor=charts.INK, loc="upper right")
    charts.style(ax, grid_axis="both")
    corr = ok[["mean", "bsi"]].corr(method="spearman").iloc[0, 1]
    charts.finish(fig, ax, "Polarisation (BSI) vs average rating: real products",
                  f"n = {len(ok):,} products with >= 20 ratings. BSI peaks around 3-3.5★ "
                  f"(Spearman rho = {corr:.2f}); a high BSI alone doesn't flag a product.", path)


def plot_variance_skew(table, path):
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.9), facecolor=charts.SURFACE)
    labels = [g.replace(" products", "\nproducts").replace("not flagged", "not flagged\nproducts") for g in table["group"]]
    colors = [charts.BLUE, charts.ORANGE, charts.BLUE, charts.ORANGE]
    for ax, metric, title in [(axes[0], "variance", "Variance (0-4)"), (axes[1], "skewness", "Skewness")]:
        ax.set_facecolor(charts.SURFACE)
        values = table[metric].to_numpy()
        ax.bar(range(len(table)), values, color=colors[:len(table)], width=0.6)
        for i, v in enumerate(values):
            ax.annotate(f"{v:.2f}", (i, v), xytext=(0, 3 if v >= 0 else -11), textcoords="offset points",
                        ha="center", fontsize=8, color=charts.INK)
        ax.set_xticks(range(len(table)), labels, fontsize=7.5)
        ax.set_title(title, loc="left", fontsize=9.5, color=charts.INK)
        ax.set_ylabel(metric)
        charts.style(ax)
        ax.axhline(0, color=charts.BASE, linewidth=0.8)
    fig.suptitle("Rating variance and skewness by review group: real sample", x=0.01, ha="left",
                 fontsize=11, color=charts.INK)
    v, f = table.set_index("group"), table.set_index("group")
    fig.text(0.01, 0.01, f"Observed. Unverified reviews are more spread out (variance {v.loc['unverified', 'variance']:.2f} "
             f"vs {v.loc['verified', 'variance']:.2f}) and less J-shaped. Flagged products are the opposite: "
             f"more 5★-heavy ({f.loc['flagged products', 'p5']:.0%} vs {f.loc['not flagged', 'p5']:.0%} 5★).",
             fontsize=7.5, color=charts.MUTED)
    fig.tight_layout(rect=(0, 0.05, 1, 0.95))
    fig.savefig(path, dpi=130, facecolor=charts.SURFACE)
    plt.close(fig)


# ---------------------------------------------------------------- main

def run(raw=RAW, out=OUT):
    if not raw.exists():
        print(f"{raw} not found: run `python analysis/download_sample.py` first. Skipping real data.")
        return None
    out.mkdir(parents=True, exist_ok=True)
    reviews, log = clean(load_amazon_jsonl(raw))
    log.insert(0, "dataset", "amazon_2023_electronics")
    log.to_csv(out / "cleaning_log_real.csv", index=False)

    products = build_product_table(reviews)
    products.to_csv(out / "products_real.csv", index=False)
    products[products["flag"]].sort_values("trust_score").to_csv(out / "flagged_products_real.csv", index=False)

    verified = verified_comparison(reviews)
    verified.to_csv(out / "verified_comparison.csv", index=False)
    by_flag = flagged_comparison(reviews, products)
    by_flag.to_csv(out / "flagged_comparison.csv", index=False)

    ok = products[products["sample_status"] == "ok"]
    high_bsi = ok["bsi"] >= 0.3
    summary = {
        "raw_lines_downloaded": 1_000_000,
        "reviews_after_cleaning": len(reviews),
        "products": len(products),
        "products_by_status": products["sample_status"].value_counts().to_dict(),
        "date_range": [str(reviews["review_date"].min().date()), str(reviews["review_date"].max().date())],
        "pct_verified_reviews": float((reviews["verified_purchase"] == "verified").mean()),
        "flagged_products": int(products["flag"].sum()),
        "flag_rate_ok_products": float(ok["flag"].mean()),
        "bands": products["band"].value_counts().to_dict(),
        "reason_counts": {name: int((ok[col] * w >= 0.05).sum()) for name, col, w in
                          [("bsi", "bsi", 0.5), ("inflation", "s_inflation", 0.7),
                           ("unverified", "s_unverified", 0.6), ("burst", "s_burst", 0.7)]},
        "burst_rate_high_bsi": float((ok.loc[high_bsi, "s_burst"] > 0).mean()),
        "burst_rate_low_bsi": float((ok.loc[~high_bsi, "s_burst"] > 0).mean()),
        "n_high_bsi": int(high_bsi.sum()),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))

    plot_verified(verified, out / "verified_vs_unverified.png")
    plot_volume(reviews, out / "review_volume_monthly.png")
    plot_trust(products, out / "trust_distribution_real.png")
    plot_bsi_vs_mean(products, out / "bsi_vs_mean_rating.png")
    plot_variance_skew(pd.concat([verified[verified["reviews"] > 0], by_flag]),
                                  out / "variance_skewness_groups.png")
    print(json.dumps(summary, indent=2, default=str))
    return reviews, log, products


if __name__ == "__main__":
    run()
