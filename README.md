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

```bash
git clone https://github.com/amritraj7237/FakeReview-Radar.git
cd FakeReview-Radar
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt

# regenerate the synthetic dataset (same seed -> same CSV)
python analysis/generate_synthetic.py --seed 42
```

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
- Chirag:
- What we learned:
- What's next:
