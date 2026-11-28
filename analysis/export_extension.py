"""Export the real-data trust scores for the browser extension.

    python analysis/export_extension.py

Reads  outputs/real/products_real.csv   (written by analyze_real.py / run_pipeline.py)
       data/raw/electronics_1000000.jsonl (optional: maps variant ASINs to their parent product)
Writes extension/data/scores.json

The extension looks a product page's ASIN up in this file. Amazon product URLs
often show a *variant* ASIN (a colour or size), while our product table is keyed
by the parent ASIN, so we also export a variant -> parent map.
"""

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PRODUCTS = ROOT / "outputs" / "real" / "products_real.csv"
RAW = ROOT / "data" / "raw" / "electronics_1000000.jsonl"
OUT = ROOT / "extension" / "data" / "scores.json"

SIGNAL_COLUMNS = {"bsi": "bsi", "inflation": "s_inflation", "unverified": "s_unverified", "burst": "s_burst"}


def _num(value, digits=6):
    """Round a number for JSON; NaN becomes null (signal not measured)."""
    return None if pd.isna(value) else round(float(value), digits)


def product_record(row):
    reasons = [row[f"reason_{i}"] for i in (1, 2, 3) if isinstance(row[f"reason_{i}"], str) and row[f"reason_{i}"]]
    return {
        "trust": None if pd.isna(row["trust_score"]) else int(row["trust_score"]),
        "band": row["band"],
        "n": int(row["n_rated"]),
        "counts": [int(row[f"count_{s}"]) for s in range(1, 6)],
        "mean": _num(row["mean"], 3),
        "pct_unverified": _num(row["pct_unverified"], 4),
        "s": {name: _num(row[col]) for name, col in SIGNAL_COLUMNS.items()},
        "reasons": reasons,
        "warning": row["warning"] if isinstance(row["warning"], str) else "",
        "dates": [str(row["first_date"])[:10], str(row["last_date"])[:10]],
    }


def variant_map(parents):
    """variant ASIN -> parent ASIN, for parents that are in our product table."""
    if not RAW.exists():
        print(f"  {RAW.name} not found: skipping the variant map (only parent ASINs will match)")
        return {}
    alias = {}
    with RAW.open(encoding="utf-8") as f:
        for line in f:
            review = json.loads(line)
            asin, parent = review.get("asin"), review.get("parent_asin")
            if asin and parent and asin != parent and parent in parents:
                alias[asin] = parent
    return alias


def main():
    if not PRODUCTS.exists():
        sys.exit(f"{PRODUCTS} not found. Run  python analysis/run_pipeline.py  first.")
    table = pd.read_csv(PRODUCTS)
    products = {row["product_id"]: product_record(row) for _, row in table.iterrows()}
    alias = variant_map(set(products))
    payload = {
        "generated": date.today().isoformat(),
        "source": "Amazon Reviews 2023, Electronics (McAuley Lab), first 1,000,000 reviews, up to March 2023",
        "flag_below": 66,
        "products": products,
        "alias": alias,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    size = OUT.stat().st_size / 1e6
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(products):,} products, {len(alias):,} variant ASINs, {size:.1f} MB")


if __name__ == "__main__":
    main()
