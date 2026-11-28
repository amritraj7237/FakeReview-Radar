# FakeReview Radar

## Project summary

FakeReview Radar looks at the *shape* of a product's star ratings, plus a few
simple signals around them (how many reviews are verified purchases, whether
reviews arrive in a sudden burst, how inflated the 5★ share is), and turns them
into a single 1–100 trust score. The goal is to flag products whose rating
pattern looks manipulated — for example a "bimodal attack" where a block of
1★ and 5★ reviews is dumped on a product in a few days — and to explain *why*
it was flagged. Because real review data has no "fake / real" labels, we also
build a synthetic dataset where we know the right answer, so we can measure how
accurate the detector is.

Polaris OJT 2026 · Data Analysis track · PST_DA_006 · Mentor: Tanishka.

**Quick look:** open [`dashboard/index.html`](dashboard/index.html) in a browser, or read the
[findings report](docs/FINDINGS_REPORT.md).

## Team

- Amrit — repo owner; synthetic data generator, Bimodal Suspicion Index, trust score
- Chirag Malik— environment, data dictionary, cleaning rules, rating metrics, data loading

## Setup

Needs **Python 3.11 or newer** (check with `python --version`; on macOS/Linux
the command may be `python3`). Run everything from the repo folder.

```bash
# 1. get the code
git clone https://github.com/amritraj7237/FakeReview-Radar.git
cd FakeReview-Radar

# 2. create a virtual environment (once) and activate it (every new terminal)
# Windows:      python -m venv .venv      then  .venv\Scripts\activate
# macOS/Linux:  python3 -m venv .venv     then  source .venv/bin/activate
#  -> your prompt now starts with (.venv)

# 3. install the exact package versions
pip install -r requirements.txt

# 4. check it worked (prints nothing and no error = OK)
python -c "import pandas, numpy, matplotlib, scipy"
pytest                          # all tests should pass

# 5. regenerate the synthetic dataset (same seed -> same CSV)
python analysis/generate_synthetic.py --seed 42
```

### Run the whole project

```bash
python analysis/download_sample.py   # once: real Amazon sample, ~572 MB into data/raw/ (git-ignored), ~2 min
python analysis/run_pipeline.py      # ~30 s: clean -> score -> evaluate -> charts -> dashboard data
```

Then open `dashboard/index.html` in a browser (double-click works, no server needed;
it loads Bootstrap and Chart.js from a CDN, so it needs internet). Without the
real sample the pipeline still runs the synthetic part and the dashboard shows
synthetic data only.

| Step | Script | Output |
|---|---|---|
| Download real sample | `analysis/download_sample.py` | `data/raw/electronics_products.jsonl` |
| Synthetic data | `analysis/generate_synthetic.py` | `data/reviews_synthetic*.csv` |
| Evaluate on labelled synthetic sets | `analysis/evaluate.py` | `outputs/evaluation/` (scores, confusion matrices, errors, charts) |
| Analyse real data | `analysis/analyze_real.py` | `outputs/real/` (cleaning log, product table, flagged CSV, charts) |
| Dashboard data | `analysis/build_dashboard.py` | `dashboard/data.js` |
| Everything above | `analysis/run_pipeline.py` | all of it |
| Browser extension data (after the pipeline) | `analysis/export_extension.py` | `extension/data/scores.json`, see [extension/README.md](extension/README.md) |

Why a virtual environment: each project gets its own package versions, so this
project can't break (or be broken by) anything else on your laptop, and anyone
can rebuild the same setup from `requirements.txt`.

**Real data sample** (not in git, ~3.5 MB). macOS/Linux, or Git Bash on Windows:

```bash
mkdir -p data/raw
curl -sL https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/review_categories/Electronics.jsonl \
  | head -n 5000 > data/raw/electronics_sample.jsonl
python analysis/inspect_sample.py      # prints the Week 1 findings, saves charts to outputs/
```

Troubleshooting:
- `python: command not found` on macOS → use `python3`.
- Windows: `activate` blocked by execution policy → run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` in PowerShell once.
- `No matching distribution found for pandas==3.1.0` → your Python is older than 3.11. Install a newer Python and recreate `.venv`.

## Project structure

```
analysis/            scripts: download, generate, evaluate, analyse, run_pipeline
analysis/radar/      reusable code: cleaning, metrics, bsi, signals, trust, products, charts
dashboard/           index.html (Bootstrap + Chart.js) and generated data.js
data/                input data; small samples only (data/raw/ is git-ignored)
docs/                definitions and write-ups (data dictionary, BSI, trust score, ...)
extension/           Chrome/Edge extension: trust-score card on Amazon product pages
tests/               automated checks
outputs/             anything our code produces (plots, reports); can always be regenerated
```

`data/` holds inputs, `outputs/` holds things our code produces. Keeping them
apart means you can delete `outputs/` at any time and rebuild it by rerunning
the code, without ever risking the source data.

## PRD checklist (must-haves)

| PRD requirement | Where |
|---|---|
| Load review data (permitted source, synthetic, fixture) | `analysis/download_sample.py`, `analysis/radar/cleaning.py`, `tests/fixtures/` |
| 1★–5★ distributions, percentages, variance, skewness | `analysis/radar/metrics.py`, `analysis/radar/products.py`, [METRICS.md](docs/METRICS.md) |
| Documented Bimodal Suspicion Index | `analysis/radar/bsi.py`, [BSI.md](docs/BSI.md) |
| Flag unusual 5★ / 1★ concentrations | BSI + 5★-inflation signals, `analysis/radar/signals.py` |
| Trust score 1–100 with documented formula | `analysis/radar/trust.py`, [TRUST_SCORE.md](docs/TRUST_SCORE.md) |
| Dashboard with rating distribution and trust score | `dashboard/index.html` |
| Test on normal and simulated suspicious data | `analysis/evaluate.py`, [EVALUATION.md](docs/EVALUATION.md) |
| Data limitations, suspicious vs proven fraud | [LIMITATIONS.md](docs/LIMITATIONS.md), [DATASET.md](docs/DATASET.md) |
| Cleaning pipeline + cleaning log | `analysis/radar/cleaning.py`, [CLEANING_RULES.md](docs/CLEANING_RULES.md) |
| Data dictionary | [DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md) |
| Automated tests for metrics and synthetic scenarios | `tests/` (run `pytest`) |
| Findings report (1–2 pages, 3–5 charts) | [FINDINGS_REPORT.md](docs/FINDINGS_REPORT.md) |

Good-to-have, also done: review-date burst detection, verified vs unverified
comparison, CSV export of flagged products (`outputs/real/flagged_products_real.csv`),
explanations for each warning. Stretch, also done: ≥ 1,000 records (393,874),
variance / skewness / kurtosis for verified vs unverified, comparative
histograms, evaluation against labelled synthetic data, and a browser extension
prototype that shows the trust score on Amazon product pages
([extension/README.md](extension/README.md)).

## Weekly log

### Week 1

- Amrit: Repo setup and scope; BSI and trust-score Maths (docs/MATH.md);
  synthetic review generator and bsi.py + tests;
  PRD problem-statement/BSI/trust-score/data-design/evaluation sections;
  Week 1 task sheets.
- Chirag: Python environment and `requirements.txt` with setup steps; data
  dictionary with raw-Amazon mapping and product table; cleaning rules with a
  10-row dirty test fixture; rating metrics (`analysis/radar/metrics.py`,
  checked against paper answers and scipy); loaded and inspected the first
  5,000 real Electronics reviews (`docs/WEEK1_FINDINGS.md`).
- What we learned: real Electronics ratings are strongly J-shaped (mostly 5★,
  a smaller 1★ bump), so a high 1★ + 5★ share on its own is normal; BSI has to
  be judged against that baseline, not against a flat distribution.
- What's next: turn the cleaning rules into code, get a much larger real sample,
  and make the synthetic generator produce separate labelled sets.

### Week 2: data foundations

- Amrit: upgraded the synthetic generator (`analysis/generate_synthetic.py`) to
  five labelled patterns (2 genuine, 3 manipulated) with a `standard` and a
  harder `hard` profile, giving separate tuning (seed 42), test (seed 7) and
  stress sets; documented it in [SYNTHETIC_DATA.md](docs/SYNTHETIC_DATA.md);
  refined `bsi.py` with small-sample shrinkage and updated [BSI.md](docs/BSI.md).
- Chirag: built the cleaning pipeline (`analysis/radar/cleaning.py`) with a
  per-rule cleaning log, updated [CLEANING_RULES.md](docs/CLEANING_RULES.md)
  and `tests/test_cleaning.py`; wrote `analysis/download_sample.py` to pull the
  first 1,000,000 Amazon Electronics lines plus product metadata; documented
  the source in [DATASET.md](docs/DATASET.md) and extended the
  [data dictionary](docs/DATA_DICTIONARY.md).
- What we learned: after cleaning, 1,000,000 raw lines become 393,874 usable
  reviews of 6,335 products; 94 % of reviews are verified purchases. The raw
  file is grouped by reviewer, so the sample is not random.
- What's next: per-product table and the warning signals.

### Week 3: signals and trust score

- Amrit: wrote the four warning signals (`analysis/radar/signals.py`: BSI,
  5★ inflation, unverified share, 7/30-day date burst) and the noisy-OR trust
  score from 1 to 100 (`analysis/radar/trust.py`, flag below 66), with
  [TRUST_SCORE.md](docs/TRUST_SCORE.md), `tests/test_signals.py` and
  `tests/test_trust.py`.
- Chirag: built the per-product table (`analysis/radar/products.py`: star
  shares, mean, variance, skewness, kurtosis, sample-size status), added
  `tests/test_scenarios.py` for the synthetic patterns, and updated
  `analysis/inspect_sample.py` for the new data layout.
- What we learned: no single signal is enough. BSI can't tell a bimodal attack
  from a genuinely divisive product, so on its own it only lowers trust to 51;
  combining signals is what pushes manipulated products below the flag line.
- What's next: measure accuracy on the labelled sets, then run on real data.

### Week 4: evaluation, real data, dashboard, report

- Amrit: wrote `analysis/evaluate.py` (confusion matrices, per-pattern and
  single-signal results, error lists for tuning / test / stress sets) and
  [EVALUATION.md](docs/EVALUATION.md); wrote [LIMITATIONS.md](docs/LIMITATIONS.md)
  (suspicious pattern vs proven fraud); co-wrote the
  [findings report](docs/FINDINGS_REPORT.md).
- Chirag: wrote `analysis/analyze_real.py` (real-data run, verified vs
  unverified comparison, flagged-products CSV) and the shared chart helpers in
  `analysis/radar/charts.py`; built the dashboard (`dashboard/index.html`,
  `analysis/build_dashboard.py`) and the one-command `analysis/run_pipeline.py`;
  updated this README; co-wrote the findings report.
- What we learned: on the test set the flag reaches 99.5 % accuracy, 100 %
  precision and 99.2 % recall, but on the stress set (small, slow attacks)
  accuracy falls to 53 % (recall 21.7 %). On real data 160 of 6,335 products
  (2.5 %) are flagged. Unverified reviews are more extreme (mean 3.90★ vs 4.30★).
- What's next: browser extension (`extension/`), and better detection of slow,
  small attacks, which rating shape alone can't catch.
