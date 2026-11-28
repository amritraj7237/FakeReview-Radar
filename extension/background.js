// Background service worker: owns the precomputed scores and answers lookups.
// The 2 MB scores file is loaded once and kept in memory; the page never sees it.
// Nothing is sent over the network: the file ships inside the extension.

let scoresPromise = null;

function loadScores() {
  if (!scoresPromise) {
    scoresPromise = fetch(chrome.runtime.getURL("data/scores.json"))
      .then((r) => r.json())
      .catch((err) => {
        scoresPromise = null; // try again next time
        throw err;
      });
  }
  return scoresPromise;
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type !== "lookup") return false;
  loadScores()
    .then((data) => {
      const id = data.products[msg.asin] ? msg.asin : data.alias[msg.asin];
      sendResponse({
        ok: true,
        productId: id || null,
        product: id ? data.products[id] : null,
        source: data.source,
      });
    })
    .catch((err) => sendResponse({ ok: false, error: String(err) }));
  return true; // we answer asynchronously
});
