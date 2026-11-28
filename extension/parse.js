// Reading a product page: the ASIN from the URL, the star histogram, the rating count.
// Pure text functions, so tests/check_port.js can test them without a browser.
//
// Amazon changes its page layout often. These parsers accept the wording Amazon
// has used ("64 percent of reviews have 5 stars", "5 star 64%", "5 stars represent
// 64% of rating"). If the layout changes, update content.js's selectors or these patterns.

const Parse = (() => {
  // /dp/ASIN, /gp/product/ASIN, /gp/aw/d/ASIN (mobile), /product-reviews/ASIN
  function findAsin(url) {
    const m = url.match(/\/(?:dp|gp\/product|gp\/aw\/d|product-reviews)\/([A-Z0-9]{10})(?:[/?#]|$)/i);
    return m ? m[1].toUpperCase() : null;
  }

  // texts: strings taken from the histogram rows (aria-labels or visible text).
  // Returns percentages for [1★, 2★, 3★, 4★, 5★], or null unless all five were found.
  function parseHistogram(texts) {
    const found = {};
    for (const raw of texts) {
      const t = String(raw).replace(/\s+/g, " ");
      const star = t.match(/\b([1-5])\s*(?:-\s*)?stars?\b/i);
      const pct = t.match(/(\d{1,3})\s*(?:%|percent)/i);
      if (!star || !pct) continue;
      const s = Number(star[1]);
      if (!(s in found)) found[s] = Number(pct[1]);
    }
    const out = [1, 2, 3, 4, 5].map((s) => found[s]);
    return out.every((v) => Number.isFinite(v) && v <= 100) ? out : null;
  }

  // "12,345 global ratings", "(1.234)", "1 rating" -> number of ratings
  function parseTotal(text) {
    const m = String(text || "").match(/\d[\d,.\s]*/);
    if (!m) return null;
    const n = Number(m[0].replace(/[^\d]/g, ""));
    return n > 0 ? n : null;
  }

  return { findAsin, parseHistogram, parseTotal };
})();

if (typeof module !== "undefined") module.exports = Parse;
