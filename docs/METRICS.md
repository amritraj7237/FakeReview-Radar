# Rating metrics: mean, variance, skewness, kurtosis

Code: [`analysis/radar/metrics.py`](../analysis/radar/metrics.py) · Tests: [`tests/test_metrics.py`](../tests/test_metrics.py) · Source: PRD sections 5 and 10

## Formulas

All four metrics come from the five star shares `p1 … p5` (the fraction of
reviews with 1★ … 5★; they sum to 1). We never need the individual reviews.

```
μ         = Σ s · p_s                       (s = 1..5)
σ²        = Σ (s − μ)² · p_s
skewness  = Σ (s − μ)³ · p_s / σ³
kurtosis  = Σ (s − μ)⁴ · p_s / σ⁴ − 3       ("excess" kurtosis: 0 for a normal bell curve)
```

These are **population** moments (divide by n, not n − 1). We describe the
reviews a product actually has rather than estimating some larger population,
and they are the same numbers `scipy.stats.skew` and `scipy.stats.kurtosis`
return with their defaults.

## Functions

| Function | Input | Returns |
|---|---|---|
| `counts_from_ratings(ratings)` | list of clean ratings (1–5) | array of 5 counts |
| `shares_from_ratings(ratings)` | list of clean ratings (1–5) | array of 5 shares that sum to 1 |
| `mean_and_variance(p)` | 5 shares that sum to 1 | `(mean, variance)` |
| `skewness(p)` | 5 shares | float, or NaN when σ = 0 |
| `kurtosis(p)` | 5 shares | float (excess), or NaN when σ = 0 |
| `rating_metrics(p)` | 5 shares | `{"mean", "variance", "skewness", "kurtosis"}` |

`mean_and_variance(p)` is the interface agreed with Amrit for the BSI. `bsi.py`
can now replace its temporary copy with
`from analysis.radar.metrics import mean_and_variance`.

The ratings helpers **raise** on anything that isn't a whole number from 1 to 5.
Cleaning (with its log) happens before metrics; see [CLEANING_RULES.md](CLEANING_RULES.md).

## What each metric means for a star chart

- **Mean:** the average star, i.e. where the chart balances.
- **Variance:** how far reviews sit from the average. It runs from 0 (everyone gave the same star) to 4 (half 1★, half 5★).
- **Skewness:** which side the long tail is on. A **negative** value means most reviews are high with a tail stretching toward 1★ (the normal J-shape). 0 means the chart is symmetric.
- **Kurtosis (excess):** whether reviews pile into one sharp peak (**positive**) or are pushed out to the two ends / spread flat (**negative**). Its lowest possible value is −2, a perfect 50/50 split between two stars.

## Paper working: charts A, B, C

Shortcut used for variance: σ² = Σ s²·p_s − μ².

**A = 8 / 4 / 7 / 17 / 64 (normal J-shape)**

```
μ  = 1(.08) + 2(.04) + 3(.07) + 4(.17) + 5(.64) = .08 + .08 + .21 + .68 + 3.20 = 4.25
Σs²p = 1(.08) + 4(.04) + 9(.07) + 16(.17) + 25(.64) = .08 + .16 + .63 + 2.72 + 16.00 = 19.59
σ² = 19.59 − 4.25² = 19.59 − 18.0625 = 1.5275
```

**B = 38 / 2 / 2 / 4 / 54 (bimodal attack)**

```
μ  = .38 + .04 + .06 + .16 + 2.70 = 3.34
Σs²p = .38 + .08 + .18 + .64 + 13.50 = 14.78
σ² = 14.78 − 3.34² = 14.78 − 11.1556 = 3.6244
```

**C = 20 / 20 / 20 / 20 / 20 (flat)**

```
μ  = .2 × (1+2+3+4+5) = 3.00
σ² = .2 × (4 + 1 + 0 + 1 + 4) = 2.00
```

### Results (code matches paper)

From `python analysis/radar/metrics.py`:

| Chart | Shares 1★…5★ (%) | Mean | σ² | Skewness | Kurtosis |
|---|---|---|---|---|---|
| A: normal J-shape | 8 / 4 / 7 / 17 / 64 | 4.25 | 1.5275 | −1.627 | +1.425 |
| B: bimodal attack | 38 / 2 / 2 / 4 / 54 | 3.34 | 3.6244 | −0.353 | −1.815 |
| C: flat | 20 / 20 / 20 / 20 / 20 | 3.00 | 2.0000 | 0.000 | −1.300 |
| Genuinely divisive | 28 / 8 / 8 / 14 / 42 | 3.34 | 2.9044 | −0.368 | −1.593 |
| All 5★ | 0 / 0 / 0 / 0 / 100 | 5.00 | 0.0000 | not defined | not defined |

## J-shape vs bimodal: what to expect

| | J-shape (A) | Bimodal (B) |
|---|---|---|
| Mean | high (≈ 4.2–4.4) | middling (≈ 3–3.5) |
| Variance | moderate (≈ 1–1.8) | high (≈ 3–4) |
| Skewness | strongly negative (≈ −1.5) | near 0 (a little negative if the 5★ end is bigger) |
| Kurtosis | positive (one sharp peak at 5★) | strongly negative (close to −2) |

**Why is kurtosis negative for B?** Kurtosis is the average of z⁴, where
z = (s − μ)/σ is how many standard deviations a review sits from the mean. In B
almost every review is a 1★ (z = −1.23) or a 5★ (z = +0.87). Nobody is near the
mean and nobody is far out in a tail, so every z⁴ is close to 1 and the average
is 1.19. Subtracting 3 gives −1.82. A J-shape is the opposite: most reviews sit
close to the mean at 5★ and the few 1★ reviews sit far out (z = −2.6, z⁴ ≈ 46),
which pushes kurtosis up.

**Why the flat chart C also has negative kurtosis and high variance:** this is
why variance and kurtosis alone cannot tell an attack from a flat or divisive
product. The BSI's valley-depth term D is there to check for an actual dip in
the middle ([BSI.md](BSI.md)).

## Check against scipy

`tests/test_metrics.py` expands each chart into 100 ratings in the right
proportions (e.g. A → eight 1s, four 2s, …, sixty-four 5s) and compares with
`scipy.stats.skew` and `scipy.stats.kurtosis`. They **agree** to floating-point
precision.

They would **disagree** if a different formula were used, which is easy to do
by accident:

| Call | A skew | A kurtosis | Why it differs |
|---|---|---|---|
| ours / `stats.skew(r)` / `stats.kurtosis(r)` | −1.6268 | 1.4249 | population moments, excess kurtosis |
| `stats.skew(r, bias=False)`, `pandas.Series.skew()` | −1.6517 | 1.5613 | sample-corrected (n − 1 style) |
| `stats.kurtosis(r, fisher=False)` | | 4.4249 | not "excess": the −3 is left out |
| `np.var(r, ddof=1)` | σ² = 1.5429 | | divides by n − 1 instead of n |

So `pandas.Series.skew()` / `.kurt()` give slightly different numbers from
ours. That's expected, not a bug. The gap shrinks as n grows.

## Edge case: every review has the same star (σ = 0)

Skewness divides by σ³ and kurtosis by σ⁴. If every review is 5★, σ = 0 and
both are 0/0. **Rule: return NaN ("not defined")**, never 0. A skewness of 0
would claim the chart is symmetric, which is a made-up value (the PRD says
never invent values). Mean (5.0) and variance (0.0) are still well defined and
returned as usual. scipy behaves the same way (it returns NaN for constant
data). The product-level table stores NaN, and the dashboard should show
"not defined (all reviews have the same star)".

Two more input rules:

- **No ratings at all:** `shares_from_ratings([])` raises, because there are no shares to compute. The product gets a low-sample warning instead (cleaning rule R8).
- **Shares that don't sum to 1, or negative:** raise `ValueError`. That always means a bug upstream.

## Viva: why is variance never above 4?

Every rating lies in [1, 5], so for any distribution σ² ≤ (5 − μ)(μ − 1). That
product is largest when μ = 3, giving 2 × 2 = 4. It is reached only when half
the reviews are 1★ and half are 5★ (every review exactly 2 stars from the
mean, and 2² = 4). `test_variance_never_above_4` checks this case.
