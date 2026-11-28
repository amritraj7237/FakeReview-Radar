// FakeReview Radar scoring, ported line by line from the Python package:
//   analysis/radar/bsi.py, analysis/radar/signals.py (bsi + inflation), analysis/radar/trust.py
// tests/check_port.js checks this file against the Python results for all 6,335 real products.
//
// On a live product page we can only see the star histogram, so only the two
// rating-shape signals (BSI and 5-star inflation) can be measured. The other two
// (unverified share, date burst) are "not measured", which noisy-OR treats as s = 0.

const Radar = (() => {
  const PRIOR = [0.08, 0.04, 0.07, 0.17, 0.64]; // typical J-shaped product
  const K = 10;                                  // shrinkage strength, in pseudo-reviews
  const TOO_SMALL = 5;                           // fewer valid ratings -> no score
  const SMALL = 20;                              // fewer -> low-sample warning
  const INFLATION_START = 0.75, INFLATION_FULL = 0.95;
  const NORMAL_4_TO_5 = PRIOR[3] / PRIOR[4];     // 0.27
  const RELIABILITY = { bsi: 0.5, inflation: 0.7, unverified: 0.6, burst: 0.7 };
  const FLAG_BELOW = 66;
  const STARS = [1, 2, 3, 4, 5];

  const sum = (a) => a.reduce((x, y) => x + y, 0);
  const ramp = (x, start, full) => Math.min(1, Math.max(0, (x - start) / (full - start)));

  function shrinkShares(counts, k = K) {
    const n = sum(counts);
    return counts.map((c, i) => (c + k * PRIOR[i]) / (n + k));
  }

  function meanAndVariance(p) {
    const mean = sum(p.map((x, i) => STARS[i] * x));
    const variance = sum(p.map((x, i) => x * (STARS[i] - mean) ** 2));
    return [mean, variance];
  }

  function bsiFromShares(p) {
    const spread = meanAndVariance(p)[1] / 4;
    const lowerPeak = Math.min(p[0], p[4]);
    const valley = lowerPeak <= 0 ? 0 : Math.max(0, 1 - (p[1] + p[2] + p[3]) / 3 / lowerPeak);
    return spread * valley;
  }

  function bsiSignal(counts) {
    if (sum(counts) < TOO_SMALL) return null;
    return bsiFromShares(shrinkShares(counts));
  }

  function inflationSignal(counts) {
    if (sum(counts) < TOO_SMALL) return null;
    const p = shrinkShares(counts);
    const excess = ramp(p[4], INFLATION_START, INFLATION_FULL);
    const ratio = p[4] > 0 ? p[3] / p[4] : 1;
    const thin4 = ramp(-ratio, -NORMAL_4_TO_5, 0);
    return excess * thin4;
  }

  // Python's round() sends 50.5 to 50; the Python code uses floor(x + 0.5), so do we.
  const roundHalfUp = (x) => Math.floor(x + 0.5);

  function combine(signals) {
    let keep = 1;
    for (const [name, s] of Object.entries(signals)) {
      if (s !== null && s !== undefined) keep *= 1 - RELIABILITY[name] * s;
    }
    return 1 - keep;
  }

  function band(trust) {
    if (trust === null) return "insufficient data";
    if (trust >= 66) return "looks genuine";
    if (trust >= 45) return "mixed signals";
    return "suspicious";
  }

  // Score from the 5 star counts only (what a product page shows).
  function scoreFromCounts(counts) {
    const n = sum(counts);
    const signals = { bsi: bsiSignal(counts), inflation: inflationSignal(counts), unverified: null, burst: null };
    if (n < TOO_SMALL) {
      return { trust: null, band: band(null), n, signals,
               warning: `Only ${n} rating(s): not enough data to score this product.` };
    }
    const trust = roundHalfUp(1 + 99 * (1 - combine(signals)));
    return {
      trust, band: band(trust), n, signals,
      warning: n < SMALL ? `Only ${n} ratings: the score is uncertain, treat it with caution.` : "",
    };
  }

  // Turn the page's rounded percentages (they rarely sum to exactly 100) and the
  // total rating count into 5 whole-number counts.
  function countsFromPercents(percents, total) {
    const s = sum(percents);
    if (!(s > 0) || !(total > 0)) return null;
    return percents.map((p) => Math.round((p / s) * total));
  }

  // Plain-language reasons, same wording style as analysis/radar/products.py.
  function reasons(counts, signals) {
    const out = [];
    const p = shrinkShares(counts);
    const pct = (x) => `${Math.round(x * 100)}%`;
    const items = Object.entries(signals)
      .filter(([, s]) => s !== null)
      .map(([name, s]) => [RELIABILITY[name] * s, name, s])
      .filter(([c]) => c >= 0.1)
      .sort((a, b) => b[0] - a[0]);
    for (const [, name, s] of items) {
      if (name === "bsi") out.push(`Ratings split into two camps: ${pct(p[0])} 1★ and ${pct(p[4])} 5★ with few in between (BSI ${s.toFixed(2)}).`);
      if (name === "inflation") out.push(`${pct(p[4])} of ratings are 5★ but only ${pct(p[3])} are 4★, more one-sided than typical products.`);
    }
    return out;
  }

  return { PRIOR, K, RELIABILITY, FLAG_BELOW, ramp, shrinkShares, meanAndVariance, bsiFromShares,
           bsiSignal, inflationSignal, combine, roundHalfUp, band, scoreFromCounts,
           countsFromPercents, reasons };
})();

if (typeof module !== "undefined") module.exports = Radar;
