# Bimodal Suspicion Index (BSI)

Code: [`analysis/radar/bsi.py`](../analysis/radar/bsi.py) · Tests: [`tests/test_bsi.py`](../tests/test_bsi.py) · Source: PRD section 9

## What it measures

A normal product's star chart is J-shaped: lots of 5★, a few 4★, and a thin tail
of 1★–3★. A **bimodal attack** looks different. Someone dumps a block of 1★ and
5★ reviews on a product, so the chart gets two tall ends and an empty middle
(a "U"). BSI is one number from 0 to 1 that says how U-shaped a chart is.

```
BSI = S × D
S   = σ² / 4                                    spread, 0 to 1
D   = max(0, 1 − mean(p2, p3, p4) / min(p1, p5))  valley depth, 0 to 1
```

`p1 … p5` are the shares of 1★ … 5★ reviews (they sum to 1).

## Why S (spread)

S is the variance of the ratings divided by 4. For ratings on a 1–5 scale the
largest possible variance is 4: it happens when half the reviews are 1★ and half
are 5★, because every review is then 2 stars from the mean of 3, and 2² = 4.
Dividing by 4 puts S on a 0 to 1 scale. S is high when reviews are pushed out to
the ends of the scale.

## Why D (valley depth)

High variance alone is **not** enough. A flat chart (20 % on every star) has a
variance of 2 (S = 0.5), but nobody is attacking it. D asks a sharper question:
*is the middle of the chart lower than both ends?* It compares the average
height of 2★/3★/4★ with the **smaller** of the two ends. Using the smaller end
matters: a valley needs a wall on both sides. A J-shape has a huge 5★ peak but a
small 1★ end, so the "valley" is not deeper than its lower wall and D = 0.

**Edge case, `min(p1, p5) = 0`:** if one end is empty there is only one peak,
so there can't be a valley between two peaks. We set **D = 0** (and avoid
dividing by zero). In practice, after shrinkage every share is above 0, so this
only happens when shrinkage is switched off (`k = 0`).

## Why multiply instead of add

We want BSI to be high only when **both** things are true: the reviews are
spread out **and** there is a real valley. Multiplying acts like an AND: if
either part is 0, BSI is 0. Adding acts like an OR, so a flat chart (S = 0.5,
D = 0) would get 0.25 just for being spread out. Multiplication also keeps the
result between 0 and 1 without any rescaling.

## Test charts

Computed with `bsi_from_shares` (no shrinkage).

| Chart | Shares 1★…5★ (%) | Mean | σ² | S | D | **BSI** |
|---|---|---|---|---|---|---|
| A: normal J-shape | 8 / 4 / 7 / 17 / 64 | 4.25 | 1.53 | 0.38 | 0.00 | **0.00** |
| Genuinely divisive | 28 / 8 / 8 / 14 / 42 | 3.34 | 2.90 | 0.73 | 0.64 | **0.47** |
| Bimodal attack | 38 / 2 / 2 / 4 / 54 | 3.34 | 3.62 | 0.91 | 0.93 | **0.84** |
| Flat / uniform | 20 / 20 / 20 / 20 / 20 | 3.00 | 2.00 | 0.50 | 0.00 | **0.00** |
| Positive stuffing | 1 / 1 / 1 / 5 / 92 | 4.86 | 0.32 | 0.08 | 0.00 | **0.00** |

The flat chart shows why D is needed (spread but no valley). The divisive chart
shows the limit of BSI: a product people truly disagree about (e.g. a polarising
book) also has a valley, so it lands in the middle (0.47). BSI raises suspicion;
other signals (unverified share, date bursts) have to confirm it.

## What BSI cannot catch: positive stuffing

If a seller floods a product with fake 5★ reviews, the chart becomes *more*
J-shaped, not U-shaped: the 1★ end shrinks, the variance drops (S = 0.08) and
there is no valley (D = 0). BSI = 0, so to BSI it looks like a very happy
product. Stuffing has to be caught by other signals: **5★ inflation** (5★
share far above the typical 64 %) and **unverified reviews**.

## Why shrinkage

A product with only a few reviews can look extreme by pure luck. Before
computing BSI we pull the shares toward a typical product:

```
p̃_s = (n · p_s + k · π_s) / (n + k),   π = (0.08, 0.04, 0.07, 0.17, 0.64),   k = 10
```

Think of it as adding k = 10 "imaginary" reviews that follow the typical
J-shape. For a product with 1,000 reviews these 10 barely matter. For a product
with 6 reviews they matter a lot, which is exactly what we want: 6 reviews are
not enough evidence to call something an attack. k = 10 means "a product needs
roughly 10 real reviews before its own shape counts as much as the prior."

**Example: a 6-review product, five 5★ and one 1★**

| | Shares 1★…5★ | σ² | S | D | **BSI** |
|---|---|---|---|---|---|
| Without shrinkage (k = 0) | 0.167 / 0 / 0 / 0 / 0.833 | 2.22 | 0.56 | 1.00 | **0.56** |
| With shrinkage (k = 10) | 0.113 / 0.025 / 0.044 / 0.106 / 0.713 | 1.79 | 0.45 | 0.48 | **0.22** |

Without shrinkage, one unhappy customer gives a perfect valley (D = 1) and a BSI
higher than the "genuinely divisive" chart. With shrinkage the score drops to
0.22, because one 1★ review out of six is weak evidence.

## BSI on the synthetic dataset (seed 42)

| Pattern | Mean BSI | Median | Max |
|---|---|---|---|
| genuine_j | 0.05 | 0.00 | 0.33 |
| genuine_divisive | 0.44 | 0.47 | 0.65 |
| bimodal_attack | 0.47 | 0.48 | 0.67 |
| positive_stuffing | 0.03 | 0.00 | 0.29 |
| burst_campaign | 0.02 | 0.00 | 0.23 |

BSI separates bimodal attacks from normal J-shaped products well. It cannot
tell them apart from naturally divisive products, and it misses stuffing and
burst campaigns. That is why BSI has only reliability c = 0.5 in the trust
score (see [TRUST_SCORE.md](TRUST_SCORE.md)) and is combined with other signals.

## Dependency note

`mean_and_variance(p)` (5 shares that sum to 1 → mean, variance) currently has a
temporary copy inside `bsi.py`. It will be replaced by Chirag's version from
Task 6 (`analysis/radar/metrics.py`) once that is merged.
