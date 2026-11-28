# FakeReview Radar browser extension

Shows a small trust-score card on Amazon product pages (Chrome or Edge,
Manifest V3). Stretch goal from PRD section 5.

The card is a **heuristic indicator, not proof**. It says which products are
worth a closer look and why, using the same formulas as the Python pipeline.

## Install (2 minutes, no store needed)

1. Make sure `extension/data/scores.json` exists. If not, run
   `python analysis/export_extension.py` from the repo folder (after `run_pipeline.py`).
2. Open `chrome://extensions` (or `edge://extensions`).
3. Turn on **Developer mode** (top right in Chrome, left sidebar in Edge).
4. Click **Load unpacked** and choose the `extension/` folder.
5. Open an Amazon product page. The card appears in the bottom-right corner.

After you change any file, click the reload icon on the extension's card in
`chrome://extensions`, then reload the Amazon tab.

## What the card shows

| Situation | What you get |
|---|---|
| The product is in our real-data sample (6,335 Electronics products, plus 18,060 colour/size variant IDs that map to them) | **Full score**: the pipeline's trust score from all 4 signals, with its reasons |
| Not in the sample, but the page shows the 1★–5★ breakdown | **Partial score** from rating shape only (BSI + 5★ inflation), labelled as partial |
| Neither | "Insufficient data" |

Try these (real products from the sample; some may no longer be listed on Amazon):

| URL | Pipeline result |
|---|---|
| amazon.com/dp/B00VXS8E8S | 31, suspicious (review burst) |
| amazon.com/dp/B0BHWQ3H17 | 64, mixed signals (5★ inflation) |
| amazon.com/dp/B01G8JO5F2 | 91, looks genuine |

## How it works

```
Amazon page ──► content.js ──(ASIN)──► background.js ──► data/scores.json
                   │                         │             (from the pipeline)
                   │   found ◄───────────────┘
                   │   └─► full score card
                   │   not found
                   └─► parse.js reads the star bars + rating count
                       radar.js computes BSI, inflation, trust ──► partial score card
```

| File | Job |
|---|---|
| `manifest.json` | Tells the browser which sites the extension runs on and which files to load |
| `content.js` | Runs inside the Amazon page: finds the product ID, asks for the score, draws the card (in a Shadow DOM so Amazon's styles can't interfere) |
| `background.js` | Loads `scores.json` once and answers lookups |
| `radar.js` | JavaScript copy of `bsi.py`, the BSI and inflation parts of `signals.py`, and `trust.py` |
| `parse.js` | Reads the product ID from the URL, and the star percentages and rating count from page text |
| `data/scores.json` | Every product's score, signals and reasons, written by `analysis/export_extension.py` |

**Why a partial score has only 2 signals:** a product page shows the star
breakdown, but not each review's verification status or date. Those would need
fetching every review page, which is slow and against the spirit of PRD
section 6 ("use only accessible pages and comply with website terms"). With
noisy-OR, signals that weren't measured count as 0, so the two missing ones
could only *lower* a partial score, never raise it.

## Checking it

```bash
python analysis/export_extension.py
node extension/tests/check_port.js
```

`check_port.js` recomputes BSI, inflation and the trust score in JavaScript for
all 6,335 products and compares them with the Python results (currently 0
differences). It also tests the URL and histogram parsers on the wording Amazon
has used.

## Privacy and limits

- **Nothing leaves the browser.** No network requests, no tracking. The extension
  only reads the page you're already looking at.
- **Amazon changes its page layout.** If the partial score stops appearing,
  the selectors in `content.js` (`HISTOGRAM_SELECTORS`, `TOTAL_SELECTORS`) or
  the patterns in `parse.js` need updating.
- **The sample is from 2023.** Full scores describe the reviews in our sample,
  not the product's reviews today.
- **Partial scores can't see bursts or unverified reviews**, which were the
  strongest signals in the evaluation. Treat them as a rough first look.
- Only Amazon is supported (the PRD lists "every e-commerce website" as out of scope).
