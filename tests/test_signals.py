import numpy as np
import pandas as pd
import pytest

from analysis.radar.products import build_product_table, score_product
from analysis.radar.signals import burst_signal, inflation_signal, ramp, unverified_signal

BIG = 10_000


def test_ramp():
    assert ramp(0.1, 0.15, 0.55) == 0
    assert ramp(0.35, 0.15, 0.55) == pytest.approx(0.5)
    assert ramp(0.9, 0.15, 0.55) == 1


def test_inflation_zero_for_normal_j_shape():
    s, _ = inflation_signal(np.array([0.08, 0.04, 0.07, 0.17, 0.64]) * BIG)
    assert s == 0


def test_inflation_high_when_almost_all_5_star_and_4_star_empty():
    s, detail = inflation_signal(np.array([0.01, 0.0, 0.01, 0.02, 0.96]) * BIG)
    assert s > 0.8
    assert detail["p5"] > 0.95


def test_inflation_needs_thin_4_star_bar():
    # 85 % 5-star but a healthy 4-star bar (ratio above the normal 0.27): not inflation
    s, _ = inflation_signal(np.array([0.01, 0.0, 0.0, 0.25, 0.74]) * BIG)
    assert s == 0


def test_unverified_ignores_unknown_and_needs_enough_reviews():
    ratings = [5, 5, 5, 4]
    assert unverified_signal(ratings, ["unknown"] * 4)[0] is None
    s, detail = unverified_signal([5] * 10, ["unknown"] * 5 + ["verified"] * 5)
    assert detail["share"] == 0 and s == 0


def test_unverified_share_and_gap():
    ratings = [5] * 50 + [1] * 25 + [5] * 25
    verified = ["verified"] * 50 + ["unverified"] * 50
    s, detail = unverified_signal(ratings, verified)
    assert detail["share"] == 0.5
    assert detail["gap"] == pytest.approx(-2.0)        # unverified mean 3 vs verified 5
    assert s == pytest.approx(ramp(0.5, 0.15, 0.55) * 1.0)


def test_burst_detects_block_and_ignores_even_spread():
    rng = np.random.default_rng(0)
    spread = pd.Timestamp("2024-01-01") + pd.to_timedelta(rng.integers(0, 365, 200), unit="D")
    assert burst_signal(spread.to_numpy())[0] == 0
    block = pd.Timestamp("2024-06-01") + pd.to_timedelta(rng.integers(0, 4, 120), unit="D")
    s, detail = burst_signal(np.concatenate([spread.to_numpy(), block.to_numpy()]))
    assert s == 1 and detail["window"] == 7


def test_burst_not_measured_with_few_dates():
    assert burst_signal(pd.to_datetime(["2024-01-01"] * 9).to_numpy())[0] is None


def test_too_small_product_gets_no_score():
    row = score_product([5, 5, 1], ["verified"] * 3, pd.to_datetime(["2024-01-01"] * 3).to_numpy())
    assert row["band"] == "insufficient data"
    assert np.isnan(row["trust_score"]) and not row["flag"]
    assert "not enough data" in row["warning"]


def test_product_table_columns_and_reasons():
    dates = pd.Timestamp("2024-01-01") + pd.to_timedelta(np.arange(60) * 6, unit="D")
    attack_dates = [pd.Timestamp("2024-05-01")] * 40
    reviews = pd.DataFrame({
        "product_id": ["P"] * 100,
        "source": "fixture",
        "rating": pd.array([5] * 45 + [4] * 10 + [1] * 5 + [1] * 18 + [5] * 22, dtype="Int64"),
        "verified_purchase": ["verified"] * 60 + ["unverified"] * 40,
        "review_date": list(dates) + attack_dates,
        "pattern": pd.NA,
    })
    table = build_product_table(reviews)
    row = table.iloc[0]
    assert row["n_rated"] == 100 and row["sample_status"] == "ok"
    assert row["count_1"] + row["count_5"] == 23 + 67
    assert row["flag"] and row["band"] == "suspicious"
    assert "within 7 days" in row["reason_1"]
