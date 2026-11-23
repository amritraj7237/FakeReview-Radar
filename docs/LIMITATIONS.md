# Limitations, and suspicious patterns vs proven fraud

Source: PRD section 5 ("document data limitations and the difference between
suspicious patterns and proven fraud") and section 16 (risks).

## Suspicious pattern ≠ proven fraud

FakeReview Radar looks at **patterns in ratings, verification and dates**. A
pattern can have an innocent cause:

| What the tool sees | Manipulation explanation | Innocent explanation |
|---|---|---|
| Two camps of 1★ and 5★ (high BSI) | competitor attack plus paid praise | a genuinely divisive product (works great or fails completely, a polarising book) |
| 5★ share far above normal, thin 4★ | bought 5★ reviews | an excellent, simple product people love |
| Many unverified reviews | fake accounts that never bought it | gifts, purchases elsewhere, early reviewer programmes |
| Many reviews in a few days | a review campaign | a launch, a sale, a viral post, a batch of reviews imported at once |

So the tool **never** says a review, reviewer or seller is fake:

- the score is a **heuristic indicator** (1–100), not a probability;
- a flag (trust < 66) means "worth a closer look", nothing more;
- every flag comes with the observed reasons, so a person can judge them;
- products with fewer than 5 ratings get no score, and 5–19 get a low-sample warning;
- reviewer IDs are only used inside the cleaning step (as part of a hashed
  review ID) and are never shown.

Proving fraud needs evidence this tool doesn't have: purchase records, account
links, IP or payment data, seller communication. That is the marketplace's job
(PRD: out of scope).

## Data limitations

1. **No ground truth on real data.** Accuracy (99.5 %) is measured on synthetic
   products we generated. On real data we can only report how many products are
   flagged (2.5 %) and why.
2. **Synthetic data is designed by us.** The attacks follow rules we wrote,
   knowing which signals we would build. The stress set shows how quickly
   accuracy drops when attacks are smaller and slower: 53 % accuracy, 21.7 % recall.
3. **Real sample is not random.** It is the first million lines of a file grouped
   by reviewer: we see each product through a subset of its reviewers, which thins
   out bursts. Only popular products (≥ 20 reviews in the sample) are included.
   Electronics only, Amazon only, up to March 2023. See [DATASET.md](DATASET.md).
4. **Amazon already filters reviews.** The most obvious fakes may be removed before
   publication, so real-data flag rates understate what exists.
5. **Only three kinds of evidence.** Ratings, verification and dates. No review
   text, reviewer history, images or seller data, so well-written fake reviews spread
   over months, from verified buyers, with a normal star shape, will not be caught.
6. **Thresholds fit Electronics.** The "normal" levels (64 % 5★, ≤ 15 % unverified,
   burst start points) come from Electronics and may not fit books, groceries or fashion.
7. **Small products are uncertain.** Shrinkage (k = 10) and the minimum-sample rules
   reduce, but don't remove, the effect of chance on products with 5–30 reviews.

## What a fair claim looks like

> "On our labelled synthetic test set, the trust-score flag identified 119 of 120
> manipulated products with no false alarms. On a sample of 6,335 real Amazon
> Electronics products it flagged 2.5 % for a closer look. These flags are
> patterns worth inspecting, not evidence of fraud."
