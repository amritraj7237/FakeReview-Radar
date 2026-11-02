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

Polaris OJT 2026 · Data Analysis track · 8 weeks.

## Team

- Amrit — repo owner; synthetic data generator, Bimodal Suspicion Index, trust score
- Chirag — environment, data dictionary, cleaning rules, rating metrics, data loading

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
analysis/            analysis scripts (e.g. generate_synthetic.py)
analysis/radar/      reusable detection code (metrics, BSI, trust score)
data/                input data; small samples only (data/raw/ is git-ignored)
docs/                definitions and write-ups (data dictionary, BSI, trust score, ...)
extension/           browser extension (later weeks)
tests/               automated checks
outputs/             anything our code produces (plots, reports); can always be regenerated
```

`data/` holds inputs, `outputs/` holds things our code produces. Keeping them
apart means you can delete `outputs/` at any time and rebuild it by rerunning
the code, without ever risking the source data.

## Weekly log

### Week 1

- Amrit:
- Chirag: Python environment and `requirements.txt` with setup steps; data
  dictionary with raw-Amazon mapping and product table; cleaning rules with a
  10-row dirty test fixture; rating metrics (`analysis/radar/metrics.py`,
  checked against paper answers and scipy); loaded and inspected the first
  5,000 real Electronics reviews (`docs/WEEK1_FINDINGS.md`).
- What we learned:
- What's next:
