# Trust score

Status: **definition only (Week 1).** The full code comes in Week 2, once real
data is available for every signal. Source: PRD; see also [BSI.md](BSI.md).

The trust score turns several suspicion signals into one number from **1 to
100**, where 100 means "looks completely genuine".

## 1. Signals and reliabilities

Each signal gives a suspicion strength **s** between 0 (nothing suspicious) and
1 (as suspicious as it gets). Each signal also has a **reliability c**: how
much we trust that signal on its own when it fires at full strength.

| Signal | What it looks at | Reliability c |
|---|---|---|
| BSI | U-shaped rating chart (bimodal attack) | 0.50 |
| 5★ inflation | 5★ share far above a typical product | 0.70 |
| Unverified reviews | share of reviews that are not verified purchases | 0.60 |
| Date burst | many reviews squeezed into a few days | 0.70 |
| Text signals | (Week 6) | — |

BSI has the lowest reliability because genuinely divisive products also score
high on it (see BSI.md). A burst or heavy 5★ inflation is harder to explain
innocently.

The exact way each raw measurement becomes `s` in 0..1 (except BSI, which is
already 0..1) will be fixed in Week 2 and tuned on the synthetic data.

## 2. Combining signals: noisy-OR

```
R     = 1 − (1 − c₁s₁)(1 − c₂s₂)…(1 − cₖsₖ)
Trust = round(1 + 99 × (1 − R))
```

Read `c·s` as "the chance this signal alone proves manipulation". Then
`(1 − c·s)` is the chance it does **not**, and the product of all of them is
the chance that *none* of the signals proves manipulation. So **R** is the
chance that *at least one* does. R = 0 gives Trust 100, R = 1 gives Trust 1.

**Rounding:** use round-half-up (`math.floor(x + 0.5)`), not Python's built-in
`round()`. Python rounds halves to the nearest even number, so `round(50.5)` is
**50**, not 51 (this matters in exercise 1 below).

## 3. Bands

| Trust | Band | Action |
|---|---|---|
| 66–100 | Looks genuine | no flag |
| 45–65 | Mixed signals | **flag** |
| 1–44 | Suspicious | **flag** |

Flag a product when **Trust < 66**.

## 4. Missing signals

If a signal can't be measured (too few reviews, no dates, no verification
info), we **skip** it. In noisy-OR, skipping is the same as setting s = 0:
a signal with s = 0 contributes the factor `(1 − c × 0) = 1`, and multiplying
by 1 changes nothing. So "we couldn't measure it" counts as "no evidence of
manipulation", never as evidence against the product.

This does **not** hold for a weighted average. There, skipping a signal changes
the denominator. For example, with only burst measured, a perfect burst gives
R = 0.7 / 0.7 = 1 and Trust 1, while with all four signals present (others 0)
the same burst gives R = 0.28 and Trust 72. The score would then depend on
which data happened to be missing.

## 5. Worked example by hand

Signals: BSI = 0.84, 5★ inflation = 0, unverified = 0.5, burst = 0.6.

| Signal | c | s | c·s | 1 − c·s |
|---|---|---|---|---|
| BSI | 0.50 | 0.84 | 0.420 | 0.580 |
| 5★ inflation | 0.70 | 0 | 0.000 | 1.000 |
| Unverified | 0.60 | 0.5 | 0.300 | 0.700 |
| Date burst | 0.70 | 0.6 | 0.420 | 0.580 |

1. Product of the last column: 0.580 × 1.000 × 0.700 × 0.580 = **0.23548**
2. R = 1 − 0.23548 = **0.76452**
3. 1 − R = 0.23548 → 1 + 99 × 0.23548 = 1 + 23.31252 = **24.31252**
4. Trust = round(24.31252) = **24** → band **Suspicious**, flagged.

## 6. Exercises

### Exercise 1: BSI alone can lower trust only to 51

BSI's worst case is s = 1 with c = 0.5, and every other signal is 0 (factor 1).

```
R     = 1 − (1 − 0.5 × 1) = 0.5
Trust = round(1 + 99 × 0.5) = round(50.5) = 51   (round half up)
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
fake-review burst passes as genuine. Noisy-OR treats each signal as an
independent chance of catching manipulation: one strong signal is enough to
pull trust down, and several weak signals add up. Signals that stay silent
don't cancel out a signal that fires, which is the behaviour we want from a
detector.
