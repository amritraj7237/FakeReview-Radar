# Trust score

Code: [`analysis/radar/signals.py`](../analysis/radar/signals.py) (signals),
[`analysis/radar/trust.py`](../analysis/radar/trust.py) (combining),
[`analysis/radar/products.py`](../analysis/radar/products.py) (one row per product + reasons) ·
Tests: [`tests/test_trust.py`](../tests/test_trust.py), [`tests/test_signals.py`](../tests/test_signals.py) ·
Source: PRD section 9. See also [BSI.md](BSI.md).

The trust score turns several warning signals into one number from **1 to
100**. Higher = fewer warning signals.

> **It is a heuristic review-quality indicator, not a probability.** A trust
> score of 30 does not mean "70 % chance of fake reviews". It means several
> independent warning signs fired, so the product is worth a closer look. It
> never proves that a seller or reviewer cheated.

## 1. Component metrics

Everything starts from the cleaned reviews of one product
([CLEANING_RULES.md](CLEANING_RULES.md)):

- the five star counts → shares p1…p5, and the **shrunk** shares
  p̃ = (n·p + k·π) / (n + k) with π = (0.08, 0.04, 0.07, 0.17, 0.64), k = 10, so
  products with few reviews are pulled toward a typical product;
- verification status: verified / unverified / unknown (unknown is never counted as unverified);
- the review dates.

## 2. The four signals and their normalisation

Each signal gives a strength **s** from 0 (nothing unusual) to 1 (as strong as
it gets), or **not measured** when there isn't enough data.

**Normalisation rule.** Except for BSI (already 0–1), every signal uses a
straight-line ramp: s = 0 up to the level that *real* products commonly reach,
rising to s = 1 at a clearly abnormal level. The "starts at" points come from
the real Amazon Electronics sample (6,316 products with ≥ 20 ratings), **not**
from the synthetic test data, so the signals are not tuned to the generator we
evaluate them with.

| Signal | Measures | s = 0 at or below | s = 1 at | Real products (median / 95th pct of the raw value) | Not measured when |
|---|---|---|---|---|---|
| **BSI** | two peaks (1★ and 5★) with an empty middle, on shrunk shares | 0 | 1 | BSI 0.00 / 0.33 | < 5 ratings |
| **5★ inflation** | p̃5 above normal **and** a thin 4★ bar | p̃5 = 0.75, or 4★:5★ ratio ≥ 0.27 | p̃5 = 0.95 and no 4★ | p̃5 0.68 / 0.83 | < 5 ratings |
| **Unverified** | share of unverified reviews, stronger with a rating gap between groups | 15 % unverified | 55 % unverified + 1★ gap | 4 % / 22 % unverified | < 5 reviews with known status |
| **Date burst** | most reviews in any 7-day or 30-day window, minus what an even spread would put there, as a share of all reviews | excess 0.15 (7 d) / 0.20 (30 d) | excess 0.35 / 0.40 | 7 d: 0.06 / 0.12 · 30 d: 0.10 / 0.19 | < 10 dated reviews |

Formulas (ramp(x, a, b) = 0 below a, 1 above b, straight line between):

```
inflation  = ramp(p̃5, 0.75, 0.95) × ramp(-(p̃4/p̃5), -0.27, 0)     both must be true
unverified = ramp(u, 0.15, 0.55) × (0.5 + 0.5 × ramp(|gap|, 0, 1))
             u = unverified / (verified + unverified),  gap = mean rating unverified − verified
             (gap only when each group has ≥ 3 ratings, otherwise the second factor is 0.5)
burst      = max over w in {7, 30} days of ramp(excess_w, start_w, start_w + 0.20)
             excess_w = (reviews in busiest w-day window − n·w/span) / n
```

Why these choices:

- **Inflation needs a thin 4★ bar.** Many genuine products are loved: 95 % of
  real products have p̃5 up to 0.83. Real happy buyers still give a fair number
  of 4★ (normal 4★:5★ ratio = 0.17/0.64 = 0.27). Bought reviews are almost all
  5★, so they push the ratio down. Requiring both keeps loved products safe.
- **15 % unverified** is where the real data's 90th percentile sits (15.6 %), and
  it is the number the full PRD uses. A high share alone counts for at most
  half; a rating gap between unverified and verified buyers adds the rest. In
  the real data unverified buyers rate 0.4★ lower on average, so a gap is
  normal in small amounts but suspicious when it is large.
- **Burst windows of 7 and 30 days.** A 7-day window catches a quick campaign;
  a 30-day window catches a slower one (positive stuffing over a month). Each
  window starts at about the 99th / 97th percentile of real products.

## 3. Reliabilities (weights)

Each signal also has a **reliability c**: how far that signal on its own may
pull the score down.

| Signal | c | Why |
|---|---|---|
| BSI | 0.50 | Polarisation has innocent causes (a genuinely divisive product), so BSI alone may never call a product "suspicious" |
| 5★ inflation | 0.70 | Hard to explain innocently once the 4★ bar disappears |
| Unverified | 0.60 | Real products vary a lot; unverified buyers aren't fake by definition |
| Date burst | 0.70 | Real reviews arrive gradually; a block in a few days is hard to explain |

## 4. Combining the signals: noisy-OR

```
R     = 1 − (1 − c₁s₁)(1 − c₂s₂)…(1 − cₖsₖ)          only measured signals
Trust = round_half_up(1 + 99 × (1 − R))
```

`(1 − c·s)` is how much of the product's "clean record" a signal leaves standing.
Multiplying them means each warning removes part of what the others left, so
one strong signal can pull the score down on its own, several weaker ones add
up, and a signal that is silent (s = 0) changes nothing. More evidence can
never raise the score. R = 0 gives Trust 100; R = 1 gives Trust 1.

The formula borrows the shape of "at least one of several independent tests
fires" from probability, but **c and s are not measured probabilities**, so
neither R nor the trust score is a probability.

**Rounding:** we use round-half-up (`math.floor(x + 0.5)`), not Python's
built-in `round()`. Python rounds halves to the nearest even number, so
`round(50.5)` is **50**, not 51 (this matters in exercise 1 below).

## 5. Bands and flag

| Trust | Band | Flag |
|---|---|---|
| 66–100 | Looks genuine | no |
| 45–65 | Mixed signals | **yes** |
| 1–44 | Suspicious | **yes** |
| (none) | Insufficient data: fewer than 5 valid ratings | no |

A product is flagged when **Trust < 66**. On the synthetic tuning set (seed 42)
66 is also the best cut-off: accuracy 88.5 % at 46, 95.5 % at 56, **97.5 % at 66**,
92.0 % at 76, 83.5 % at 86.

## 6. Missing data

- A signal that can't be measured (too few ratings, too few dated reviews,
  verification all unknown) is **skipped** and listed as "not measured".
- **Skipping is the same as s = 0** in noisy-OR: the factor is `(1 − c × 0) = 1`,
  and multiplying by 1 changes nothing. So missing data never counts as evidence
  against a product.
- A weighted average would behave badly here: the denominator changes with the
  signals present. With only burst measured, a perfect burst gives R = 0.7 / 0.7
  = 1 (Trust 1); with all four present (others 0) the same burst gives R = 0.28
  (Trust 72). The score would depend on which data happened to be missing.
- **Fewer than 5 valid ratings:** every rating signal is "not measured", which
  would give a meaningless 100. Such products get **no score** and the band
  "insufficient data". 5–19 ratings get a score plus a low-sample warning.

## 7. Reasons shown to the user

Every measured signal with c·s ≥ 0.10 becomes a plain-language reason, the
three largest first, for example:

- "11 of 22 dated reviews (50%) arrived within 30 days from 2016-07-12."
- "68% of reviews are not verified purchases (typical: under 15%); unverified reviewers rate 0.8★ lower on average."
- "Ratings split into two camps: 39% 1★ and 42% 5★ with few in between (BSI 0.70)."

They describe what was observed; they never say a review is fake.

## 8. Worked example by hand

Signals: BSI = 0.84, 5★ inflation = 0, unverified = 0.5, burst = 0.6.

| Signal | c | s | c·s | 1 − c·s |
|---|---|---|---|---|
| BSI | 0.50 | 0.84 | 0.420 | 0.580 |
| 5★ inflation | 0.70 | 0 | 0.000 | 1.000 |
| Unverified | 0.60 | 0.5 | 0.300 | 0.700 |
| Date burst | 0.70 | 0.6 | 0.420 | 0.580 |

1. Product of the last column: 0.580 × 1.000 × 0.700 × 0.580 = **0.23548**
2. R = 1 − 0.23548 = **0.76452**
3. 1 + 99 × 0.23548 = 1 + 23.31252 = **24.31252**
4. Trust = round_half_up(24.31252) = **24** → band **Suspicious**, flagged.

`tests/test_trust.py` checks this example.

## 9. Exercises

### Exercise 1: BSI alone can lower trust only to 51

BSI's worst case is s = 1 with c = 0.5, and every other signal is 0 (factor 1).

```
R     = 1 − (1 − 0.5 × 1) = 0.5
Trust = round_half_up(1 + 99 × 0.5) = round_half_up(50.5) = 51
```

Since s ≤ 1, c·s ≤ 0.5, so R ≤ 0.5 and Trust ≥ 51 whenever BSI is the only
signal firing. 51 is in the "mixed signals" band: BSI on its own can raise a
flag but can never call a product "suspicious". That is intended, because a
genuinely divisive product can have a high BSI.

### Exercise 2: Why noisy-OR and not a weighted average?

Test case: **perfect burst, nothing else** (burst s = 1, all other s = 0).

| Method | R | Trust | Band |
|---|---|---|---|
| Noisy-OR | 1 − (1 − 0.7) = 0.70 | round(1 + 99 × 0.30) = **31** | Suspicious |
| Weighted average (weights = c) | (0.7 × 1) / (0.5 + 0.7 + 0.6 + 0.7) = 0.28 | round(1 + 99 × 0.72) = **72** | Looks genuine |

The weighted average **dilutes** strong evidence: one clear red flag gets
averaged with three signals that just didn't fire, and a product with a perfect
fake-review burst passes as genuine. Noisy-OR lets one strong signal pull trust
down, lets several weak signals add up, and silent signals don't cancel out a
signal that fires.

## 10. Does it work? (summary, details in [EVALUATION.md](EVALUATION.md))

| Data | Result |
|---|---|
| Synthetic test set (seed 7, never used for tuning) | accuracy 99.5 %, precision 100 %, recall 99.2 % |
| Synthetic stress set (smaller, slower attacks) | accuracy 53.0 %, precision 100 %, recall 21.7 % |
| Real Electronics sample (no labels) | 160 of 6,335 products (2.5 %) flagged for a closer look |
