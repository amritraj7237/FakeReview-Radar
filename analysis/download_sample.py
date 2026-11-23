"""Download a sample of Amazon Reviews 2023 (Electronics) and keep products with enough reviews.

The full Electronics file is 22.6 GB, so we stream the first --lines lines and stop.
The file is grouped by reviewer (in no particular order), so the first N lines are
all the reviews of a set of reviewers. For each product that means we see a
subset of its reviewers, which keeps the rating shape but thins out the dates.

Step 1 writes the raw lines:          data/raw/electronics_<lines>.jsonl
Step 2 keeps only products with at least --min-reviews reviews in that sample:
                                      data/raw/electronics_products.jsonl

Both files are in data/raw/, which is git-ignored (research-use licence, too big for git).

Usage:
    python analysis/download_sample.py                      # 1,000,000 lines, products with >= 20 reviews
    python analysis/download_sample.py --lines 5000 --out data/raw/electronics_sample.jsonl --no-filter
"""

import argparse
import json
import time
import urllib.request
from collections import Counter
from pathlib import Path

URL = ("https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/"
       "raw/review_categories/Electronics.jsonl")


def download_lines(url, n_lines, out_path):
    """Stream the first n_lines lines of url into out_path."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()
    written = 0
    with urllib.request.urlopen(url) as response, open(out_path, "wb") as out:
        for line in response:
            out.write(line)
            written += 1
            if written % 100_000 == 0:
                print(f"  {written:,} lines ({time.time() - start:.0f} s)")
            if written >= n_lines:
                break
    print(f"Wrote {written:,} lines to {out_path}")
    return written


def keep_products(in_path, out_path, min_reviews):
    """Write only the reviews of products that have at least min_reviews reviews."""
    with open(in_path, encoding="utf-8") as f:
        counts = Counter(json.loads(line)["parent_asin"] for line in f)
    keep = {pid for pid, n in counts.items() if n >= min_reviews}
    kept_rows = 0
    with open(in_path, encoding="utf-8") as f, open(out_path, "w", encoding="utf-8") as out:
        for line in f:
            if json.loads(line)["parent_asin"] in keep:
                out.write(line)
                kept_rows += 1
    print(f"{len(counts):,} products in sample; kept {len(keep):,} with >= {min_reviews} "
          f"reviews ({kept_rows:,} reviews) in {out_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lines", type=int, default=1_000_000)
    parser.add_argument("--out", default=None, help="raw output (default data/raw/electronics_<lines>.jsonl)")
    parser.add_argument("--min-reviews", type=int, default=20)
    parser.add_argument("--products-out", default="data/raw/electronics_products.jsonl")
    parser.add_argument("--no-filter", action="store_true", help="only download, skip step 2")
    args = parser.parse_args()

    raw = Path(args.out or f"data/raw/electronics_{args.lines}.jsonl")
    if raw.exists():
        print(f"{raw} already exists, skipping download")
    else:
        download_lines(URL, args.lines, raw)
    if not args.no_filter:
        keep_products(raw, Path(args.products_out), args.min_reviews)


if __name__ == "__main__":
    main()
