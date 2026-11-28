// Checks that extension/radar.js gives the same numbers as the Python pipeline.
//
//   python analysis/export_extension.py      (writes extension/data/scores.json)
//   node extension/tests/check_port.js
//
// For every real product: BSI and 5-star inflation recomputed in JavaScript from
// the star counts must match the Python values, and noisy-OR over all four
// Python signal strengths must give the same trust score and band.

const fs = require("fs");
const path = require("path");
const Radar = require("../radar.js");
const { parseHistogram, parseTotal, findAsin } = require("../parse.js");

const data = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "data", "scores.json"), "utf8"));
let checked = 0, failures = 0;
const fail = (msg) => { failures++; if (failures <= 10) console.log("FAIL", msg); };
const close = (a, b) => Math.abs(a - b) < 1e-5;

for (const [id, p] of Object.entries(data.products)) {
  checked++;
  const bsi = Radar.bsiSignal(p.counts);
  const infl = Radar.inflationSignal(p.counts);
  if (!close(bsi, p.s.bsi)) fail(`${id} bsi js=${bsi} py=${p.s.bsi}`);
  if (!close(infl, p.s.inflation)) fail(`${id} inflation js=${infl} py=${p.s.inflation}`);
  if (p.trust !== null) {
    const trust = Radar.roundHalfUp(1 + 99 * (1 - Radar.combine(p.s)));
    if (trust !== p.trust) fail(`${id} trust js=${trust} py=${p.trust}`);
    if (Radar.band(trust) !== p.band) fail(`${id} band js=${Radar.band(trust)} py=${p.band}`);
  }
}

// Worked example from docs/TRUST_SCORE.md section 8, and the BSI-only floor of 51.
const worked = Radar.roundHalfUp(1 + 99 * (1 - Radar.combine({ bsi: 0.84, inflation: 0, unverified: 0.5, burst: 0.6 })));
if (worked !== 24) fail(`worked example gave ${worked}, expected 24`);
const bsiOnly = Radar.roundHalfUp(1 + 99 * (1 - Radar.combine({ bsi: 1, inflation: 0, unverified: 0, burst: 0 })));
if (bsiOnly !== 51) fail(`BSI-only floor gave ${bsiOnly}, expected 51`);

// Page parsing on text in the formats Amazon has used.
const h1 = parseHistogram(["64 percent of reviews have 5 stars", "17 percent of reviews have 4 stars",
  "7 percent of reviews have 3 stars", "4 percent of reviews have 2 stars", "8 percent of reviews have 1 stars"]);
if (JSON.stringify(h1) !== "[8,4,7,17,64]") fail(`aria-label histogram parsed as ${h1}`);
const h2 = parseHistogram(["5 star 70%", "4 star 12%", "3 star 6%", "2 star 3%", "1 star 9%"]);
if (JSON.stringify(h2) !== "[9,3,6,12,70]") fail(`row-text histogram parsed as ${h2}`);
const h3 = parseHistogram(["5 stars represent 55% of rating", "4 stars represent 20% of rating", "3 stars represent 10% of rating", "2 stars represent 5% of rating", "1 star represents 10% of rating"]);
if (JSON.stringify(h3) !== "[10,5,10,20,55]") fail(`"represent" histogram parsed as ${h3}`);
if (parseHistogram(["5 star 70%", "4 star 12%"]) !== null) fail("incomplete histogram should be null");
if (parseTotal("12,345 global ratings") !== 12345) fail("total with comma");
if (parseTotal("(1.234)") !== 1234) fail("total with dot separator");
if (findAsin("https://www.amazon.com/Some-Name/dp/B07N69T6TM/ref=sr_1_1?th=1") !== "B07N69T6TM") fail("dp url");
if (findAsin("https://www.amazon.in/gp/product/B01G8JO5F2") !== "B01G8JO5F2") fail("gp/product url");
if (findAsin("https://www.amazon.com/s?k=headphones") !== null) fail("search page should have no ASIN");

console.log(`${checked} products checked, ${failures} failure(s)`);
process.exit(failures ? 1 : 0);
