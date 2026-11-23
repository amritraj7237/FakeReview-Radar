"""Evaluate the trust-score flag on labelled synthetic data (PRD section 10, evaluation method).

Three synthetic sets, each generated independently:

    tuning   seed 42, standard profile   used while choosing the signal settings
    test     seed 7,  standard profile   never looked at while tuning: the headline result
    stress   seed 7,  hard profile       smaller, slower, better-hidden attacks the rules
                                         were never tuned on

A product is predicted "manipulated" when its trust score is below 66 (the flag).
For each set we report accuracy, precision, recall, F1, specificity and the
confusion matrix, the flag rate per pattern, every false positive / negative with
its reasons, and how well each signal does on its own.

Usage:
    python analysis/evaluate.py            # writes outputs/evaluation/*
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.generate_synthetic import PATTERNS, generate  # noqa: E402
from analysis.radar import charts  # noqa: E402
from analysis.radar.cleaning import SOURCE_SYNTHETIC, clean, load_csv  # noqa: E402
from analysis.radar.products import build_product_table  # noqa: E402
from analysis.radar.trust import FLAG_BELOW, RELIABILITY, trust_score  # noqa: E402

SETS = {
    "tuning": {"seed": 42, "profile": "standard", "csv": "data/reviews_synthetic.csv"},
    "test":   {"seed": 7,  "profile": "standard", "csv": "data/reviews_synthetic_test_seed7.csv"},
    "stress": {"seed": 7,  "profile": "hard",     "csv": "data/reviews_synthetic_hard_seed7.csv"},
}
SIGNAL_COLUMNS = {"bsi": "bsi", "inflation": "s_inflation", "unverified": "s_unverified", "burst": "s_burst"}
OUT = Path("outputs/evaluation")


def scores(y_true, y_pred):
    y_true, y_pred = np.asarray(y_true, bool), np.asarray(y_pred, bool)
    tp = int((y_true & y_pred).sum())
    fp = int((~y_true & y_pred).sum())
    tn = int((~y_true & ~y_pred).sum())
    fn = int((y_true & ~y_pred).sum())
    precision = tp / (tp + fp) if tp + fp else float("nan")
    recall = tp / (tp + fn) if tp + fn else float("nan")
    return {
        "products": len(y_true), "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "accuracy": (tp + tn) / len(y_true),
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else float("nan"),
        "specificity": tn / (tn + fp) if tn + fp else float("nan"),
    }


def load_set(name):
    """Regenerate a synthetic set (same seed -> same file), clean it, build its product table."""
    spec = SETS[name]
    path = Path(spec["csv"])
    generate(seed=spec["seed"], profile=spec["profile"]).to_csv(path, index=False)
    reviews, log = clean(load_csv(path, source=SOURCE_SYNTHETIC))
    return reviews, log, build_product_table(reviews)


def per_pattern(products):
    table = products.groupby("pattern").agg(
        products=("product_id", "count"),
        manipulated=("is_manipulated_product", "first"),
        flagged=("flag", "sum"),
        median_trust=("trust_score", "median"),
    ).reindex(PATTERNS)
    table["flag_rate"] = table["flagged"] / table["products"]
    return table.reset_index()


def single_signal(products):
    """How each signal does alone: trust from that one signal, same < 66 flag."""
    rows = []
    for name, col in SIGNAL_COLUMNS.items():
        s = products[col].fillna(0.0)
        alone = s.map(lambda v: trust_score(RELIABILITY[name] * v)) < FLAG_BELOW
        row = {"signal": name, **scores(products["is_manipulated_product"], alone)}
        for pattern in PATTERNS:
            mask = products["pattern"] == pattern
            row[f"mean_s_{pattern}"] = products.loc[mask, col].mean()
            row[f"flag_rate_{pattern}"] = alone[mask].mean()
        rows.append(row)
    return pd.DataFrame(rows)


def errors(products):
    wrong = products[products["flag"] != products["is_manipulated_product"]].copy()
    wrong["error"] = np.where(wrong["flag"], "false positive", "false negative")
    cols = ["error", "product_id", "pattern", "n_rated", "trust_score", "bsi", "s_inflation",
            "s_unverified", "s_burst", "reason_1", "reason_2", "reason_3"]
    return wrong[cols].sort_values(["error", "pattern", "trust_score"])


# ---------------------------------------------------------------- charts

def plot_confusion(result, name, path):
    fig, ax = charts.new_figure(4.6, 4.0)
    grid = np.array([[result["tn"], result["fp"]], [result["fn"], result["tp"]]])
    top = grid.max()
    for (i, j), value in np.ndenumerate(grid):
        shade = charts.SEQUENTIAL[min(int(value / top * 6), 6)] if top else charts.SEQUENTIAL[0]
        ax.add_patch(__import__("matplotlib").patches.FancyBboxPatch(
            (j + 0.03, 1 - i + 0.03), 0.94, 0.94, boxstyle="round,pad=0,rounding_size=0.04",
            facecolor=shade, edgecolor=charts.SURFACE, linewidth=2))
        ax.text(j + 0.5, 1 - i + 0.5, f"{value}", ha="center", va="center", fontsize=16,
                color="#ffffff" if value / max(top, 1) > 0.5 else charts.INK)
    ax.set_xlim(0, 2)
    ax.set_ylim(0, 2)
    ax.set_xticks([0.5, 1.5], ["not flagged", "flagged (trust < 66)"])
    ax.set_yticks([1.5, 0.5], ["genuine", "manipulated"])
    ax.set_xlabel("prediction")
    ax.set_ylabel("ground truth")
    charts.style(ax, grid_axis=None)
    for side in ["left", "bottom"]:
        ax.spines[side].set_visible(False)
    charts.finish(fig, ax, f"Confusion matrix: {name} set",
                  f"n = {result['products']} synthetic products. Accuracy {result['accuracy']:.1%}, "
                  f"precision {result['precision']:.1%}, recall {result['recall']:.1%}.", path)


def plot_trust_by_pattern(products, name, path):
    fig, ax = charts.new_figure(7.4, 4.2)
    rng = np.random.default_rng(0)
    for x, pattern in enumerate(PATTERNS):
        rows = products[products["pattern"] == pattern]
        color = charts.ORANGE if rows["is_manipulated_product"].iloc[0] else charts.BLUE
        jitter = rng.uniform(-0.18, 0.18, len(rows))
        ax.scatter(x + jitter, rows["trust_score"].astype(float), s=16, color=color,
                   edgecolor=charts.SURFACE, linewidth=0.6, zorder=3)
        ax.hlines(rows["trust_score"].median(), x - 0.3, x + 0.3, color=charts.INK, linewidth=1.5, zorder=4)
    ax.axhline(FLAG_BELOW - 0.5, color=charts.CRITICAL, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(len(PATTERNS) - 0.5, FLAG_BELOW + 1, "flag line: trust < 66", ha="right", va="bottom",
            fontsize=7.5, color=charts.MUTED)
    ax.set_xticks(range(len(PATTERNS)), [p.replace("_", "\n") for p in PATTERNS])
    ax.set_ylim(0, 103)
    ax.set_ylabel("trust score (1-100)")
    ax.scatter([], [], color=charts.BLUE, s=16, label="genuine (simulated)")
    ax.scatter([], [], color=charts.ORANGE, s=16, label="manipulated (simulated)")
    ax.legend(frameon=False, fontsize=8, loc="lower left", labelcolor=charts.INK)
    charts.style(ax)
    charts.finish(fig, ax, f"Trust score by simulated pattern: {name} set",
                  f"n = {len(products)} synthetic products (40 per pattern); black bar = median. "
                  "Simulated labels, not real fraud.", path)


def plot_signal_heatmap(products, name, path):
    import matplotlib.patches as patches
    fig, ax = charts.new_figure(6.6, 3.8)
    means = products.groupby("pattern")[list(SIGNAL_COLUMNS.values())].mean().reindex(PATTERNS)
    for i, pattern in enumerate(PATTERNS):
        for j, col in enumerate(SIGNAL_COLUMNS.values()):
            v = means.loc[pattern, col]
            shade = charts.SEQUENTIAL[min(int(v * 7), 6)]
            ax.add_patch(patches.FancyBboxPatch((j + 0.03, len(PATTERNS) - 1 - i + 0.04), 0.94, 0.92,
                         boxstyle="round,pad=0,rounding_size=0.04", facecolor=shade,
                         edgecolor=charts.SURFACE, linewidth=2))
            ax.text(j + 0.5, len(PATTERNS) - 1 - i + 0.5, f"{v:.2f}", ha="center", va="center",
                    fontsize=9, color="#ffffff" if v > 0.45 else charts.INK)
    ax.set_xlim(0, len(SIGNAL_COLUMNS))
    ax.set_ylim(0, len(PATTERNS))
    ax.set_xticks(np.arange(len(SIGNAL_COLUMNS)) + 0.5, list(SIGNAL_COLUMNS))
    ax.set_yticks(np.arange(len(PATTERNS)) + 0.5, PATTERNS[::-1])
    ax.set_xlabel("signal (mean strength s, 0-1)")
    charts.style(ax, grid_axis=None)
    for side in ["left", "bottom"]:
        ax.spines[side].set_visible(False)
    charts.finish(fig, ax, f"Which signal fires for which pattern: {name} set",
                  f"n = {len(products)} synthetic products. Each attack lights up a different "
                  "mix of signals, which is why they are combined.", path)


# ---------------------------------------------------------------- main

def run(out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    summary, logs, datasets = {}, [], {}
    for name in SETS:
        reviews, log, products = load_set(name)
        datasets[name] = (reviews, products)
        log.insert(0, "dataset", f"synthetic_{name}")
        logs.append(log)
        result = scores(products["is_manipulated_product"], products["flag"])
        summary[name] = {**SETS[name], **result}
        products.to_csv(out / f"products_{name}.csv", index=False)
        per_pattern(products).to_csv(out / f"per_pattern_{name}.csv", index=False)
        single_signal(products).to_csv(out / f"single_signal_{name}.csv", index=False)
        errors(products).to_csv(out / f"errors_{name}.csv", index=False)
        if name != "tuning":
            plot_confusion(result, name, out / f"confusion_{name}.png")
            plot_trust_by_pattern(products, name, out / f"trust_by_pattern_{name}.png")
        if name == "test":
            plot_signal_heatmap(products, name, out / "signal_heatmap_test.png")
        print(f"{name:7s} accuracy {result['accuracy']:.1%}  precision {result['precision']:.1%}  "
              f"recall {result['recall']:.1%}  F1 {result['f1']:.3f}  "
              f"(TP {result['tp']}, FP {result['fp']}, TN {result['tn']}, FN {result['fn']})")
    pd.concat(logs).to_csv(out / "cleaning_log_synthetic.csv", index=False)
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary, datasets


if __name__ == "__main__":
    run()
