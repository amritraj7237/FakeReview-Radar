# Data dictionary

Source: PRD section 7, extended. Covers the **review-level table** (one row per
review, both real and synthetic data), how raw Amazon fields map onto it, and
the **product-level table** (one row per product) that the metrics, BSI and
trust score fill in.

Sources referred to below:

- **Amazon**: Amazon Reviews 2023, Electronics (McAuley Lab, Hugging Face), `raw/review_categories/Electronics.jsonl`
- **Synthetic**: `data/reviews_synthetic.csv` from `analysis/generate_synthetic.py`
- **Derived**: computed by our pipeline

## 1. Review-level table

| Column | Type | Example | Description | Allowed values / range | Missing values | Source |
|---|---|---|---|---|---|---|
| `review_id` | string | `AMZ-3f1c9a0b7e2d4c11` / `SYN0001-R0001` | Unique review identifier | unique per row | Amazon has no ID, so we build one (see §3). A missing ID is flagged; we deduplicate only when a reliable key exists | Derived (Amazon), Synthetic |
| `product_id` | string | `B083NRGZMM` / `SYN0001` | Product identifier = `parent_asin`, so colour/size variants of one product are pooled | non-empty | Required for product-level analysis. Rows without it are kept but excluded from product tables and counted in the log | Amazon `parent_asin`, Synthetic |
| `rating` | integer (nullable `Int64`) | `5` | Star rating | whole number 1–5 | Invalid or missing ratings are set to NA, excluded from rating calculations and counted in the cleaning log (R1, R2) | Amazon `rating`, Synthetic |
| `review_date` | date | `2022-07-18` | Date the review was submitted (UTC) | 1995-01-01 to the dataset's collection end (we use 2023-12-31 for Amazon) | Missing or invalid dates → NA, excluded from time-based analysis only (R4) | Amazon `timestamp`, Synthetic |
| `verified_purchase` | categorical | `verified` | Whether the platform marked it as a verified purchase | `verified` / `unverified` / `unknown` | Missing stays **`unknown`**, never treated as unverified (R5) | Amazon `verified_purchase`, Synthetic |
| `review_text` | string | `These didn't work. Idk if…` | Review body | any text | Empty kept for rating analysis, excluded from text analysis (R6) | Amazon `text` |
| `review_title` | string | `Smells like gasoline!` | Review headline | any text | Optional; empty allowed | Amazon `title` |
| `reviewer_id` | string | `AFKZENTNBQ7A7V7UXW5JJI6UGRYQ` | Pseudonymous reviewer identifier | any | Optional. Used only for de-duplication and the review_id key, **never to identify individuals** | Amazon `user_id` |
| `helpful_votes` | integer (nullable `Int64`) | `18` | Helpful votes the review received | ≥ 0 | Missing treated as **unknown (NA), not zero** | Amazon `helpful_vote` |
| `source` | string | `amazon_2023_electronics` / `synthetic` | Dataset the row came from | `amazon_2023_electronics`, `synthetic`, later `handbuilt` | Required for traceability; never missing (set by loader) | Derived |
| `pattern` | string | `bimodal_attack` | Ground-truth pattern of the product | `genuine_j`, `genuine_divisive`, `bimodal_attack`, `positive_stuffing`, `burst_campaign` | NA for real data (not present) | Synthetic only |
| `is_manipulated_product` | boolean | `True` | Ground truth: product has an injected block | True / False | NA for real data | Synthetic only |
| `is_injected` | boolean | `False` | Ground truth: this review was injected | True / False | NA for real data | Synthetic only |

The synthetic CSV stores `verified_purchase` as `True` / `False` and has no
text, title, reviewer or helpful-vote columns. The loader maps
`True → verified`, `False → unverified` and fills the text columns with NA.

## 2. Raw Amazon field → our column

Raw record (one JSON object per line):

```json
{"rating": 3.0, "title": "...", "text": "...", "images": [], "asin": "B083NRGZMM",
 "parent_asin": "B083NRGZMM", "user_id": "AFKZ...", "timestamp": 1658185117948,
 "helpful_vote": 0, "verified_purchase": true}
```

| Raw field | Raw type | Our column | Conversion needed |
|---|---|---|---|
| `rating` | float (`3.0`) | `rating` | Must be a whole number 1–5, then cast to `Int64`. `3.5`, `0`, `7` or missing → NA + log (R1/R2) |
| `title` | string | `review_title` | Strip whitespace; `""` → NA |
| `text` | string | `review_text` | Strip whitespace; `""` → NA (R6) |
| `parent_asin` | string | `product_id` | none |
| `asin` | string | *(not kept)* | Variant-level ID (colour/size). In the sample, 2,245 of 5,000 rows have `asin ≠ parent_asin`. We analyse per `parent_asin` |
| `user_id` | string | `reviewer_id` | none |
| `timestamp` | int, **milliseconds** since 1970-01-01 UTC | `review_date` | `pd.to_datetime(ts, unit="ms", utc=True).dt.date`. Read the JSON with `dtype=False` so pandas doesn't guess (R7) |
| `helpful_vote` | int | `helpful_votes` | Cast to `Int64`; missing stays NA |
| `verified_purchase` | bool | `verified_purchase` | `True → "verified"`, `False → "unverified"`, missing → `"unknown"` |
| `images` | list | *(not kept)* | Not needed for rating analysis |
| *(none)* | | `review_id` | Built from `user_id + parent_asin + timestamp` (§3) |
| *(none)* | | `source` | Constant `"amazon_2023_electronics"` |

## 3. Decision: building a stable `review_id`

The raw data has no review ID. We build one that gives the **same ID every
time the same review is loaded**, whatever order the file is read in:

```
review_id = "AMZ-" + sha1(f"{user_id}|{parent_asin}|{timestamp}").hexdigest()[:16]
```

- **Why these three fields:** one person reviews one product at one millisecond. Together they identify a review. None of them changes between downloads.
- **Why a hash and not a plain join:** the joined string is ~55 characters and contains the reviewer ID. The PRD says reviewer IDs are never used to identify people, so we don't want them copied into every chart, CSV export and extension payload. 16 hex characters (64 bits) make an accidental collision in millions of rows practically impossible.
- **Why not the row number:** row numbers change whenever we take a different sample or the file is re-sorted.
- **Collision rule:** if two rows get the same ID but have **different text**, they are not duplicates. The second gets a suffix `-2`, `-3`, … and the case is counted in the log. If the text is also the same, it's a true duplicate (R3).
- **Checked on the sample:** no two of the 5,000 rows share `user_id + parent_asin + timestamp`.

Synthetic data keeps the generator's IDs (`SYN0001-R0001`).

## 4. Product-level table (one row per product)

Built from the cleaned review table, grouped by `product_id` (and `source`).

| Column | Type | Example | Description | Range / notes |
|---|---|---|---|---|
| `product_id` | string | `SYN0041` | Product (= `parent_asin`) | key |
| `source` | string | `synthetic` | Dataset | as above |
| `n_reviews` | int | `212` | Review rows after duplicates removed | ≥ 1 |
| `n_rated` | int | `210` | Rows with a valid rating, used for every rating metric | ≤ `n_reviews` |
| `count_1` … `count_5` | int | `81, 4, 4, 9, 112` | Number of 1★ … 5★ reviews | sum = `n_rated` |
| `p1` … `p5` | float | `0.386, 0.019, …` | Raw shares `count_s / n_rated` (**not** shrunk; shrinkage happens inside the BSI) | 0–1, sum = 1 |
| `mean` | float | `3.34` | Average star | 1–5 |
| `variance` | float | `3.62` | σ² (population) | 0–4 |
| `skewness` | float | `−0.35` | Third standardised moment | NaN when variance = 0 |
| `kurtosis` | float | `−1.82` | Excess kurtosis | ≥ −2; NaN when variance = 0 |
| `n_verified`, `n_unverified`, `n_unknown` | int | `40, 160, 12` | Verification counts | sum = `n_reviews` |
| `pct_unverified` | float | `0.79` | `n_unverified / (n_verified + n_unverified)`; unknown excluded from both | NaN if all unknown |
| `first_date`, `last_date` | date | `2025-01-03` | Earliest / latest valid review date | NaN if no valid dates |
| `sample_status` | categorical | `ok` | `too_small` (< 5 rated), `small` (5–19), `ok` (≥ 20) | see R8 |
| `bsi` | float | `0.84` | Bimodal Suspicion Index after shrinkage ([BSI.md](BSI.md)) | 0–1; NaN if `too_small` |
| `s_inflation`, `s_unverified`, `s_burst` | float | `0, 0.5, 0.6` | Signal strengths (Week 2) | 0–1; NaN = not measured |
| `signals_not_measured` | string | `burst` | Signals skipped for missing data | may be empty |
| `trust_score` | int | `24` | Heuristic score ([TRUST_SCORE.md](TRUST_SCORE.md)) | 1–100 |
| `flag` | boolean | `True` | `trust_score < 66` | |
| `pattern`, `is_manipulated_product` | string / bool | `bimodal_attack`, `True` | Ground truth, copied from reviews | synthetic only, NA for real |

Text features (near-duplicate share, sentiment mismatch, fake-text
probability) are added in Week 6.
