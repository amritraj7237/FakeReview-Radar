"""Write dashboard/data.js: everything the HTML dashboard shows, as one JavaScript object.

A .js file (not .json) so dashboard/index.html works when opened straight from
disk, without a web server. Called by analysis/run_pipeline.py.

Real data: every flagged product plus a fixed random sample of the rest (the full
table is outputs/real/products_real.csv). Synthetic: every test and stress product.
"""

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from analysis.generate_synthetic import PATTERNS
from analysis.radar.metrics import STARS
from analysis.radar.trust import BANDS, FLAG_BELOW, RELIABILITY

OUT = Path("dashboard/data.js")
REAL_UNFLAGGED_SAMPLE = 340
GROUPS = ["verified", "unverified", "unknown"]


def _num(x, digits=4):
    if x is None or (isinstance(x, float) and np.isnan(x)) or x is pd.NA:
        return None
    if isinstance(x, (float, np.floating)):
        return round(float(x), digits)
    if isinstance(x, (np.integer,)):
        return int(x)
    return x


def _weekly(dates):
    """Sparse weekly counts: [[week number since 1970, count], ...]."""
    weeks = (pd.to_datetime(dates).dropna().astype("int64") // (7 * 86_400 * 10**9)).astype(int)
    counts = weeks.value_counts().sort_index()
    return [[int(w), int(c)] for w, c in counts.items()]


def product_records(reviews, products):
    by_id = {pid: g for pid, g in reviews.groupby("product_id", sort=False)}
    records = []
    for row in products.itertuples(index=False):
        g = by_id[row.product_id]
        split = []
        for group in GROUPS:
            r = g.loc[g["verified_purchase"] == group, "rating"].dropna().astype(int)
            split.append(np.bincount(r, minlength=6)[1:].tolist())
        rec = {
            "id": row.product_id,
            "n": int(row.n_reviews),
            "rated": int(row.n_rated),
            "status": row.sample_status,
            "counts": [int(getattr(row, f"count_{s}")) for s in STARS],
            "split": split,
            "mean": _num(row.mean), "variance": _num(row.variance),
            "skewness": _num(row.skewness), "kurtosis": _num(row.kurtosis),
            "pctUnverified": _num(row.pct_unverified),
            "s": {"bsi": _num(row.bsi), "inflation": _num(row.s_inflation),
                  "unverified": _num(row.s_unverified), "burst": _num(row.s_burst)},
            "risk": _num(row.risk),
            "trust": _num(row.trust_score) if not pd.isna(row.trust_score) else None,
            "band": row.band,
            "flag": bool(row.flag),
            "reasons": [r for r in (row.reason_1, row.reason_2, row.reason_3) if r],
            "warning": row.warning,
            "first": None if pd.isna(row.first_date) else str(row.first_date.date()),
            "last": None if pd.isna(row.last_date) else str(row.last_date.date()),
            "weeks": _weekly(g["review_date"]),
        }
        if hasattr(row, "pattern") and isinstance(row.pattern, str):
            rec["pattern"] = row.pattern
            rec["manipulated"] = bool(row.is_manipulated_product)
        records.append(rec)
    return records


def table(df):
    return json.loads(df.to_json(orient="records"))


def build(real, synthetic, summary, out=OUT):
    data = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "method": {"reliability": RELIABILITY, "flagBelow": FLAG_BELOW,
                   "bands": [{"from": lo, "name": name} for lo, name in BANDS]},
        "datasets": {},
        "evaluation": {"summary": summary, "patterns": PATTERNS},
    }
    eval_dir = Path("outputs/evaluation")
    for name in ["test", "stress"]:
        reviews, products = synthetic[name]
        data["datasets"][name] = {
            "label": f"Synthetic {name} set (seed {summary[name]['seed']}, {summary[name]['profile']})",
            "kind": "synthetic",
            "products": product_records(reviews, products),
        }
        data["evaluation"][name] = {
            "perPattern": table(pd.read_csv(eval_dir / f"per_pattern_{name}.csv")),
            "singleSignal": table(pd.read_csv(eval_dir / f"single_signal_{name}.csv")),
            "errors": table(pd.read_csv(eval_dir / f"errors_{name}.csv").fillna("")),
        }
    data["cleaningLogs"] = {"synthetic": table(pd.read_csv(eval_dir / "cleaning_log_synthetic.csv").fillna(""))}

    if real is not None:
        reviews, log, products = real
        flagged = products[products["flag"]]
        rest = products[~products["flag"]].sample(
            n=min(REAL_UNFLAGGED_SAMPLE, (~products["flag"]).sum()), random_state=1)
        shown = pd.concat([flagged, rest])
        real_dir = Path("outputs/real")
        data["datasets"]["real"] = {
            "label": "Real: Amazon Reviews 2023, Electronics",
            "kind": "real",
            "products": product_records(reviews[reviews["product_id"].isin(shown["product_id"])], shown),
            "summary": json.loads((real_dir / "summary.json").read_text()),
            "verified": table(pd.read_csv(real_dir / "verified_comparison.csv")),
            "trustHistogram": np.histogram(products["trust_score"].dropna().astype(float),
                                           bins=np.arange(0.5, 101.5, 5))[0].tolist(),
            "monthly": [[str(k.date()), int(v)] for k, v in reviews.dropna(subset=["review_date"])
                        .set_index("review_date").resample("MS").size()["2005":].items()],
        }
        data["cleaningLogs"]["real"] = table(log.fillna(""))

    out.parent.mkdir(exist_ok=True)
    out.write_text("// Generated by analysis/run_pipeline.py. Do not edit by hand.\n"
                   f"window.RADAR = {json.dumps(data, separators=(',', ':'))};\n", encoding="utf-8")
    print(f"Wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")
