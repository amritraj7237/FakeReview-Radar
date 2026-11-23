"""Run the whole project end to end.

    python analysis/run_pipeline.py

1. Generate the synthetic sets (tuning seed 42, test seed 7, stress seed 7 hard),
   clean them, score every product and evaluate the flag  -> outputs/evaluation/
2. Clean, score and analyse the real Amazon sample, if downloaded -> outputs/real/
   (get it with: python analysis/download_sample.py)
3. Write the dashboard data -> dashboard/data.js, then open dashboard/index.html
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis import analyze_real, build_dashboard, evaluate  # noqa: E402


def main():
    start = time.time()
    print("== 1. Synthetic data: clean, score, evaluate")
    summary, synthetic = evaluate.run()
    print("\n== 2. Real Amazon Electronics sample")
    real = analyze_real.run()
    print("\n== 3. Dashboard data")
    build_dashboard.build(real, synthetic, summary)
    print(f"\nDone in {time.time() - start:.0f} s. Open dashboard/index.html in a browser.")


if __name__ == "__main__":
    main()
