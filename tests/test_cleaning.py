"""The cleaning code must reproduce the expected numbers in docs/CLEANING_RULES.md."""

import pandas as pd
import pytest

from analysis.radar.cleaning import clean, load_csv, make_review_id, sample_status

FIXTURE = "tests/fixtures/dirty_sample.csv"


@pytest.fixture(scope="module")
def cleaned():
    return clean(load_csv(FIXTURE))


def rule_total(log, rule):
    return int(log.loc[log["rule"] == rule, "rows_affected"].sum())


@pytest.mark.parametrize("rule, expected", [
    ("R7_date_normalized", 1),
    ("R4_invalid_date", 1),
    ("R3_duplicate", 2),
    ("R1_rating_out_of_range", 1),
    ("R2_rating_missing", 1),
    ("R5_verification_unknown", 1),
    ("R6_text_missing", 1),
    ("R0_missing_product_id", 0),
    ("R0_missing_review_id", 0),
    ("R8_low_sample_too_small", 1),
    ("R8_low_sample_small", 1),
])
def test_log_counts_match_cleaning_rules_doc(cleaned, rule, expected):
    _, log = cleaned
    assert rule_total(log, rule) == expected


def test_duplicates_split_by_key(cleaned):
    _, log = cleaned
    dup = log[log["rule"] == "R3_duplicate"].set_index("detail")["rows_affected"]
    assert dup.filter(like="key (a)").sum() == 1
    assert dup.filter(like="key (b)").sum() == 1


def test_rows_and_ratings_left(cleaned):
    reviews, _ = cleaned
    assert len(reviews) == 8
    assert sorted(reviews["review_id"]) == ["R01", "R02", "R03", "R06", "R07", "R08", "R09", "R10"]
    rated = reviews.loc[reviews["rating"].notna(), "review_id"]
    assert sorted(rated) == ["R01", "R06", "R07", "R08", "R09", "R10"]


def test_row_level_outcomes(cleaned):
    reviews, _ = cleaned
    row = reviews.set_index("review_id")
    assert pd.isna(row.loc["R02", "rating"])
    assert pd.isna(row.loc["R06", "review_date"])
    assert row.loc["R06", "rating"] == 4                    # bad date, rating still usable
    assert row.loc["R07", "verified_purchase"] == "unknown"  # never turned into "unverified"
    assert row.loc["R03", "verified_purchase"] == "unverified"
    assert pd.isna(row.loc["R08", "review_text"])
    assert row.loc["R09", "review_date"] == pd.Timestamp("2022-07-18")


def test_every_rule_logged_even_when_zero(cleaned):
    _, log = cleaned
    assert {"R0_missing_product_id", "R0_missing_review_id"} <= set(log["rule"])
    assert log["step"].tolist() == list(range(1, len(log) + 1))


def test_sample_status_thresholds():
    assert [sample_status(n) for n in (0, 4, 5, 19, 20)] == \
        ["too_small", "too_small", "small", "small", "ok"]


def test_review_id_is_stable_and_hides_reviewer():
    a = make_review_id("AFKZENTNBQ7A7V7UXW5JJI6UGRYQ", "B083NRGZMM", 1658185117948)
    assert a == make_review_id("AFKZENTNBQ7A7V7UXW5JJI6UGRYQ", "B083NRGZMM", 1658185117948)
    assert a.startswith("AMZ-") and len(a) == 20
    assert "AFKZ" not in a


def test_pre_2001_unix_timestamps_have_fewer_digits():
    raw = pd.DataFrame({
        "review_id": ["ms12", "s9", "s10"], "product_id": "P", "rating": "5",
        "review_date": ["939081600000", "939081600", "1658185117"],   # 1999-10-05 (ms, s), 2022-07-18 (s)
        "verified_purchase": "True", "source": "amazon_2023_electronics",
    })
    reviews, log = clean(raw)
    assert reviews["review_date"].dt.strftime("%Y-%m-%d").tolist() == ["1999-10-05", "1999-10-05", "2022-07-18"]
    assert rule_total(log, "R4_invalid_date") == 0


def test_out_of_range_dates_for_amazon():
    raw = pd.DataFrame({
        "review_id": ["a", "b", "c"], "product_id": ["P", "P", "P"], "rating": ["5", "4", "3"],
        "review_date": ["0", "1658185117948", "1735689600000"],  # 1970, 2022, 2025
        "verified_purchase": ["True", "False", "True"], "source": "amazon_2023_electronics",
    })
    reviews, log = clean(raw)
    assert reviews["review_date"].notna().tolist() == [False, True, False]
    assert rule_total(log, "R4_invalid_date") == 2
