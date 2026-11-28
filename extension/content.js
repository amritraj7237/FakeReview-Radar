// Runs on Amazon pages. On a product page it shows a small FakeReview Radar card:
//   1. ASIN found in our real-data sample -> full score (4 signals) from the pipeline.
//   2. Otherwise -> partial score from the star histogram visible on the page
//      (BSI + 5-star inflation only; verification and dates aren't on the page).
// The card lives in a Shadow DOM so Amazon's CSS can't change it, and vice versa.

(() => {
  const HISTOGRAM_SELECTORS = [
    "#histogramTable",
    "#cm_cr_dp_d_rating_histogram",
    "[data-hook='rating-histogram']",
    "#reviewsMedley",
  ];
  const TOTAL_SELECTORS = [
    "[data-hook='total-review-count']",
    "#acrCustomerReviewText",
    "#acrCustomerReviewLink",
  ];
  const SIGNAL_LABELS = { bsi: "Two camps (BSI)", inflation: "5★ inflation", unverified: "Unverified share", burst: "Review burst" };

  const CSS = `
    :host { all: initial; }
    .card {
      position: fixed; right: 16px; bottom: 16px; z-index: 2147483647;
      width: 320px; max-width: calc(100vw - 32px); max-height: calc(100vh - 32px); overflow: auto;
      background: #ffffff; color: #15202b; border: 1px solid #d9dfe6; border-radius: 12px;
      box-shadow: 0 8px 28px rgba(0,0,0,.18);
      font: 13px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif;
    }
    .top { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border-bottom: 1px solid #e6eaef; }
    .top strong { font-size: 13px; color: #0b6884; letter-spacing: .02em; }
    .actions { display: flex; gap: 4px; }
    button { all: unset; cursor: pointer; width: 24px; height: 24px; text-align: center; border-radius: 6px; font-size: 16px; line-height: 24px; color: #586676; }
    button:hover, button:focus-visible { background: #edf1f4; }
    .collapsed .body { display: none; }
    .body { padding: 12px; display: grid; gap: 10px; }
    .score { display: flex; gap: 12px; align-items: center; }
    .num { font-size: 40px; font-weight: 700; line-height: 1; font-variant-numeric: tabular-nums; }
    .num.good { color: #2b7a4b; } .num.warn { color: #a8670f; } .num.bad { color: #b8382a; } .num.none { color: #586676; }
    .pill { display: inline-block; padding: 2px 9px; border-radius: 999px; font-weight: 600; font-size: 12px; text-transform: capitalize; }
    .pill.good { background: #e3f3e9; color: #2b7a4b; } .pill.warn { background: #faf0dc; color: #a8670f; }
    .pill.bad { background: #f9e4e1; color: #b8382a; } .pill.none { background: #edf1f4; color: #586676; }
    .muted { color: #586676; font-size: 12px; margin: 0; }
    .mode { font-size: 12px; background: #e2f0f4; padding: 6px 8px; border-radius: 6px; }
    .mode.partial { background: #faf0dc; }
    .warnbox { font-size: 12px; background: #f9e4e1; padding: 6px 8px; border-radius: 6px; }
    .sigs { display: grid; gap: 4px; }
    .sig { display: grid; grid-template-columns: 112px 1fr 34px; gap: 8px; align-items: center; font-size: 12px; }
    .sig .nm { grid-column: 2 / 4; color: #8a96a3; font-style: italic; }
    .bar { height: 6px; background: #edf1f4; border-radius: 3px; overflow: hidden; }
    .bar i { display: block; height: 100%; background: #0b6884; }
    .v { text-align: right; font-variant-numeric: tabular-nums; color: #586676; }
    ul { margin: 0; padding-left: 18px; display: grid; gap: 4px; }
    .foot { margin: 0; font-size: 11px; color: #586676; }
  `;

  let lastAsin = null;
  let host = null;
  const dismissed = new Set();

  // ---------- reading the page

  function pageAsin() {
    return Parse.findAsin(location.href) ||
      document.querySelector("input#ASIN, input[name='ASIN']")?.value?.toUpperCase() || null;
  }

  function histogramFromPage() {
    for (const sel of HISTOGRAM_SELECTORS) {
      const root = document.querySelector(sel);
      if (!root) continue;
      const texts = [];
      root.querySelectorAll("[aria-label]").forEach((el) => texts.push(el.getAttribute("aria-label")));
      root.querySelectorAll("tr, li, a").forEach((el) => texts.push(el.innerText || el.textContent || ""));
      const percents = Parse.parseHistogram(texts);
      if (percents) return percents;
    }
    return null;
  }

  function totalFromPage() {
    for (const sel of TOTAL_SELECTORS) {
      const n = Parse.parseTotal(document.querySelector(sel)?.textContent);
      if (n) return n;
    }
    return null;
  }

  // ---------- the card

  function bandClass(band) {
    return { "looks genuine": "good", "mixed signals": "warn", "suspicious": "bad" }[band] || "none";
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }

  function signalRows(signals) {
    return Object.entries(SIGNAL_LABELS).map(([key, label]) => {
      const s = signals[key];
      if (s === null || s === undefined) {
        return `<div class="sig"><span>${label}</span><span class="nm">not measured</span></div>`;
      }
      const pull = Radar.RELIABILITY[key] * s;
      return `<div class="sig"><span>${label}</span><span class="bar"><i style="width:${Math.round(pull / 0.7 * 100)}%"></i></span><span class="v">${s.toFixed(2)}</span></div>`;
    }).join("");
  }

  function render(view) {
    if (!host) {
      host = document.createElement("div");
      host.id = "fakereview-radar-host";
      host.attachShadow({ mode: "open" });
      document.documentElement.appendChild(host);
    }
    const trust = view.trust === null ? "–" : view.trust;
    const reasons = view.reasons.length
      ? `<ul>${view.reasons.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>`
      : `<p class="muted">No warning signal is strong enough to list.</p>`;
    host.shadowRoot.innerHTML = `
      <style>${CSS}</style>
      <div class="card" role="complementary" aria-label="FakeReview Radar">
        <div class="top">
          <strong>FakeReview Radar</strong>
          <span class="actions">
            <button class="min" title="Minimise" aria-label="Minimise">–</button>
            <button class="close" title="Hide on this product" aria-label="Hide on this product">×</button>
          </span>
        </div>
        <div class="body">
          <div class="score">
            <span class="num ${bandClass(view.band)}">${trust}</span>
            <span><span class="pill ${bandClass(view.band)}">${esc(view.band)}</span><br>
            <span class="muted">trust score, 1–100 (heuristic)</span></span>
          </div>
          <div class="mode ${view.partial ? "partial" : ""}">${esc(view.mode)}</div>
          ${view.warning ? `<div class="warnbox">${esc(view.warning)}</div>` : ""}
          <div class="sigs">${signalRows(view.signals)}</div>
          ${reasons}
          <p class="foot">A pattern worth a closer look, not proof that reviews are fake. ${esc(view.footnote)}</p>
        </div>
      </div>`;
    const card = host.shadowRoot.querySelector(".card");
    host.shadowRoot.querySelector(".min").addEventListener("click", () => card.classList.toggle("collapsed"));
    host.shadowRoot.querySelector(".close").addEventListener("click", () => {
      dismissed.add(view.asin);
      host.remove();
      host = null;
    });
  }

  function removeCard() {
    if (host) { host.remove(); host = null; }
  }

  // ---------- deciding what to show

  function lookup(asin) {
    return new Promise((resolve) => {
      try {
        chrome.runtime.sendMessage({ type: "lookup", asin }, (res) => {
          resolve(chrome.runtime.lastError ? null : res);
        });
      } catch (e) {
        resolve(null); // extension reloaded while the page was open
      }
    });
  }

  async function update() {
    const asin = pageAsin();
    if (asin === lastAsin) return;
    lastAsin = asin;
    if (!asin || dismissed.has(asin)) { removeCard(); return; }

    const res = await lookup(asin);
    if (asin !== lastAsin) return; // user moved on while we waited

    if (res?.ok && res.product) {
      const p = res.product;
      render({
        asin,
        trust: p.trust, band: p.band, signals: p.s,
        reasons: p.reasons, warning: p.warning, partial: false,
        mode: `Full score: 4 signals from ${p.n.toLocaleString()} reviews in our sample (${p.dates[0]} to ${p.dates[1]}).`,
        footnote: `Source: ${res.source}.`,
      });
      return;
    }

    const percents = histogramFromPage();
    const total = totalFromPage();
    const counts = percents && total ? Radar.countsFromPercents(percents, total) : null;
    if (!counts) {
      render({
        asin, trust: null, band: "insufficient data",
        signals: { bsi: null, inflation: null, unverified: null, burst: null },
        reasons: [], warning: "", partial: true,
        mode: "This product isn't in our sample, and the star breakdown couldn't be read from this page.",
        footnote: "",
      });
      return;
    }
    const r = Radar.scoreFromCounts(counts);
    render({
      asin, trust: r.trust, band: r.band, signals: r.signals,
      reasons: Radar.reasons(counts, r.signals), warning: r.warning, partial: true,
      mode: `Partial score: rating shape only (2 of 4 signals), from the ${total.toLocaleString()} ratings shown on this page. Verification and review dates aren't visible here.`,
      footnote: "The two missing signals could only lower this score, never raise it.",
    });
  }

  // Amazon changes the URL without a page load when you pick a colour or size,
  // and the histogram can load late, so check again now and then.
  update();
  let tries = 0;
  setInterval(() => {
    if (pageAsin() !== lastAsin) { update(); return; }
    // retry a few times if the histogram wasn't on the page yet
    const mode = host?.shadowRoot?.querySelector(".mode")?.textContent || "";
    if (mode.includes("couldn't be read") && tries++ < 5) { lastAsin = null; update(); }
  }, 1500);
})();
