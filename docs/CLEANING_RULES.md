# Cleaning rules

Source: PRD section 8. Column names follow [DATA_DICTIONARY.md](DATA_DICTIONARY.md).
Test fixture: [`tests/fixtures/dirty_sample.csv`](../tests/fixtures/dirty_sample.csv).

## Two principles

1. **Never silently delete.** Every row that is removed or left out of a calculation is counted in the cleaning log. The only rows actually removed are exact duplicates (R3), and their IDs are logged too.
2. **Never invent values.** A missing value stays missing (NA / `"unknown"`). We never fill it with a guess such as 0, `False` or an average.

**Why missing `verified_purchase` becomes `"unknown"` and not `False`:** if we
turned unknowns into "unverified", every review with missing metadata would
land in the unverified group. That group would look bigger and its ratings
different for no real reason, and the unverified-reviews signal would fire on
products that just have patchy data.

## The cleaning log

The pipeline writes one row per rule per run to `outputs/cleaning_log.csv`, even when
nothing was affected (a 0 proves the check ran):

| Column | Example |
|---|---|
| `step` | `3` |
| `rule` | `R3_duplicate` |
| `column` | `review_id` |
| `action` | `removed` / `excluded_from_rating` / `excluded_from_time` / `set_unknown` / `excluded_from_text` / `normalized` / `flagged` |
| `rows_affected` | `2` |
| `example_ids` | `R04;R05` (up to 5 review_ids, so a person can look them up) |
| `source` | `amazon_2023_electronics` |

## Rules, in the order they run

Order matters. Dates are normalised before duplicate checks (which compare dates).
Duplicates go before the rating counts, so a duplicated bad rating isn't
counted twice.

### R7. Inconsistent date formats (runs first)

- **Problem:** dates arrive as Unix milliseconds (`1658185117948`, Amazon), ISO strings (`2025-01-10`, synthetic) or occasionally Unix seconds.
- **Detect:** for each raw date value: all digits with 13 characters → Unix ms. All digits with 10 characters → Unix seconds. Otherwise try `pd.to_datetime(value, format="ISO8601")`.
- **Action:** convert all of them to a UTC calendar date in `review_date`. Anything that fails goes to R4.
- **Log:** `R7_date_normalized`, rows converted from a non-ISO format (per format).

### R4. Invalid date

- **Problem:** date is missing, can't be parsed (`2023-02-30`, `"yesterday"`), or is outside 1995-01-01 … collection end (e.g. a timestamp of 0 → 1970).
- **Detect:** `review_date` is NaT after R7, or `< 1995-01-01`, or `> 2023-12-31` for Amazon.
- **Action:** set `review_date` to NA. The row **stays** for rating and verification metrics and is left out of time-based analysis (bursts, volume over time).
- **Log:** `R4_invalid_date`, rows with a date excluded.

### R3. Duplicate review records

- **Problem:** the same review appears twice (download overlap, re-scrape).
- **Detect:** either (a) `review_id` repeated, or (b) same `reviewer_id + product_id + review_text + review_date` with a different `review_id`. Use `df.duplicated(subset=..., keep="first")`. For (b) only rows where all four are non-missing count, because two NA texts aren't proof of a duplicate.
- **Action:** **remove** later copies and keep the first. This is the only rule that removes rows.
- **Log:** `R3_duplicate`, duplicates removed, with their review_ids. Key (a) and key (b) get separate log rows.

### R1. Rating outside 1–5

- **Problem:** rating is `0`, `7`, `-1` or `3.5`.
- **Detect:** rating is not NaN and not in `{1, 2, 3, 4, 5}` (`~df.rating.isin([1,2,3,4,5]) & df.rating.notna()`).
- **Action:** set `rating` to NA, so the row is excluded from rating calculations. **Keep the row** for verification and date analysis.
- **Log:** `R1_rating_out_of_range`, rows excluded.

### R2. Missing rating

- **Problem:** rating is empty.
- **Detect:** `df.rating.isna()` on the raw value (counted before R1 adds its own NAs, so the two counts don't overlap).
- **Action:** exclude from rating metrics and keep the row.
- **Log:** `R2_rating_missing`, rows excluded.

### R5. Missing purchase verification

- **Problem:** `verified_purchase` is empty or not a recognisable true/false value.
- **Detect:** value not in `{True, False, "true", "false", "verified", "unverified"}` (case-insensitive), or NA.
- **Action:** set to `"unknown"`. Unknown rows are a third group in the verified/unverified comparison and are left out of `pct_unverified`.
- **Log:** `R5_verification_unknown`, rows labelled unknown.

### R6. Missing review text

- **Problem:** `review_text` is NA or only whitespace.
- **Detect:** `df.review_text.isna() | (df.review_text.str.strip() == "")`.
- **Action:** set to NA. Keep the row for rating analysis and exclude it from text analysis (Week 6).
- **Log:** `R6_text_missing`, rows without text. Synthetic data has no text, so this rule is skipped for `source == "synthetic"` and the log says so.

### R0. Missing product_id or review_id (from the data dictionary)

- **Detect:** `product_id` or `review_id` NA or empty.
- **Action:** a missing `product_id` keeps the row but leaves it out of every product-level table. A missing `review_id` is flagged, and duplicates can then only be caught by key (b).
- **Log:** `R0_missing_product_id`, `R0_missing_review_id`, rows flagged.

### R8. Very small review sample (product level, runs last)

- **Problem:** a product has too few valid ratings for its shape to mean anything.
- **Detect:** `n_rated` per product (after R1–R3).
- **Action:**
  - `n_rated < 5`: `sample_status = "too_small"`. Sample-based signals (BSI, inflation, burst) are **"not measured"**, and the product gets a low-sample warning.
  - `5 ≤ n_rated < 20`: `sample_status = "small"`. Scored, but excluded from cross-product comparisons (histograms across products, threshold tuning).
  - `n_rated ≥ 20`: `ok`.
- **Log:** `R8_low_sample`, number of products in each status (products, not rows).

## Expected result on `tests/fixtures/dirty_sample.csv`

10 rows, one problem each (R01 is the clean reference row):

| Row | Problem planted | Rule | Expected outcome |
|---|---|---|---|
| R01 | none | | kept, all fields valid |
| R02 | rating `7` | R1 | kept, rating → NA |
| R03 | rating empty | R2 | kept, rating NA |
| R04 | exact copy of R01 (same review_id) | R3 (a) | removed |
| R05 | same reviewer + product + text + date as R01, new ID | R3 (b) | removed |
| R06 | date `2023-02-30` | R4 | kept, review_date → NA |
| R07 | verified_purchase empty | R5 | kept, → `unknown` |
| R08 | review_text empty | R6 | kept, text NA |
| R09 | date as Unix ms `1658185117948` | R7 | kept, review_date → `2022-07-18` |
| R10 | only review of product `P002` | R8 | P002 → `too_small` |

Expected log counts: R7 = 1, R4 = 1, R3 = 2 (1 by key a, 1 by key b),
R1 = 1, R2 = 1, R5 = 1, R6 = 1, R0 = 0. 8 rows remain, 6 of them with a usable
rating (R01, R06, R07, R08, R09, R10). Products: P001 has 5 rated rows →
`small`, P002 has 1 → `too_small`. The Week 2 cleaning code must reproduce exactly these numbers.
