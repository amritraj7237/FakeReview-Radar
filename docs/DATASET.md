# Dataset documentation

Source: PRD section 6 ("record dataset version, source, fields and licence";
"record count, collection period, refresh frequency, missing fields and known
sampling biases").

## Real data: Amazon Reviews 2023, Electronics

| Item | Value |
|---|---|
| Dataset | Amazon Reviews 2023, McAuley Lab (UCSD), hosted on Hugging Face as `McAuley-Lab/Amazon-Reviews-2023` |
| File | `raw/review_categories/Electronics.jsonl` (22.6 GB, one JSON review per line) |
| Licence / terms | Released for research use. We only download it for this analysis, keep the raw files out of git (`data/raw/` is ignored) and publish only aggregate results |
| Fields used | `rating`, `title`, `text`, `parent_asin`, `user_id`, `timestamp` (Unix ms), `helpful_vote`, `verified_purchase`. Not used: `asin` (variant), `images` |
| Retrieval script | [`analysis/download_sample.py`](../analysis/download_sample.py) |
| Refresh frequency | None. A fixed 2023 release; collection stopped in 2023 |

### Our sample

| Item | Value |
|---|---|
| How taken | First **1,000,000 lines** of the file (streamed, ~572 MB, ~100 s), then only products with ≥ 20 reviews in those lines |
| Kept | **6,335 products**, **395,016 reviews** before cleaning, **393,874** after (1,149 duplicates removed) |
| Collection period in the sample | 1998-03-03 to 2023-03-20 (97 % from 2013 onwards; busiest month January 2020) |
| Reviews per product | median 33 valid ratings (range 18 to 5,195; 19 products fell below 20 after duplicates were removed) |
| Verification | 94.0 % verified, 6.0 % unverified, 0 unknown |

### Missing fields and data quality (cleaning log: `outputs/real/cleaning_log_real.csv`)

| Check | Rows |
|---|---|
| Rating missing or outside 1–5 | 0 |
| Invalid or missing date | 0 |
| Duplicate review_id (same user + product + millisecond) | 993 removed |
| Duplicate user + product + text + date | 156 removed |
| Verification missing | 0 |
| Empty review text | 75 (kept for ratings) |
| Products with 5–19 valid ratings after cleaning | 19 (score + low-sample warning) |

### Known sampling biases

1. **Grouped by reviewer.** The file lists all reviews of one reviewer together, in no obvious order.
   The first million lines are all the reviews of 185,242 reviewers. For each product we therefore see the
   reviews of *those* reviewers only, a subset of its real reviews. Rating shapes should be roughly
   representative; **bursts are thinned out**, because a real burst is spread over many reviewers, most of
   whom are not in our sample.
2. **Popular products only.** Keeping products with ≥ 20 reviews in the sample favours products with
   thousands of reviews overall. Small sellers, where manipulation may be more common, are under-represented.
3. **Electronics only, Amazon only, up to 2023.** Results shouldn't be generalised to other categories,
   shops or later years.
4. **No labels.** We don't know which real reviews are fake, so real-data numbers describe what the tool
   flags, not how accurate it is.
5. **Amazon's own filtering.** Amazon removes some fake reviews before publishing, so the data already
   lacks the most obvious cases.

## Synthetic data

See [SYNTHETIC_DATA.md](SYNTHETIC_DATA.md): how each of the five patterns is
generated, the seeds, and the "hard" stress profile.

## Week 1 sample (historical)

Week 1 used the first 5,000 lines only ([WEEK1_FINDINGS.md](WEEK1_FINDINGS.md)).
That sample had 4,509 products and none with ≥ 20 reviews, and its 67 %
verified share came from a few heavy reviewers. The 1,000,000-line sample
replaces it for all product-level work.
