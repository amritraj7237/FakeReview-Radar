"""Synthetic scenarios end to end: generate -> clean -> score. Uses its own seed (123),
different from the tuning (42) and test (7) seeds."""

import pandas as pd
import pytest

from analysis.generate_synthetic import generate
from analysis.radar.cleaning import clean
from analysis.radar.products import build_product_table


@pytest.fixture(scope="module")
def products():
    raw = generate(seed=123, products_per_pattern=15)
    raw = raw.astype({"rating": str, "is_manipulated_product": str, "is_injected": str})
    reviews, log = clean(raw)
    assert log["rows_affected"][log["rule"].str.startswith(("R1", "R2", "R3", "R4"))].sum() == 0
    return build_product_table(reviews)


def flag_rate(products, pattern):
    return products.loc[products["pattern"] == pattern, "flag"].mean()


def test_generator_is_reproducible():
    pd.testing.assert_frame_equal(generate(seed=5, products_per_pattern=2), generate(seed=5, products_per_pattern=2))
    assert not generate(seed=5, products_per_pattern=2).equals(generate(seed=6, products_per_pattern=2))


def test_generator_uses_data_dictionary_values():
    df = generate(seed=5, products_per_pattern=2)
    assert set(df["verified_purchase"]) <= {"verified", "unverified"}
    assert df["rating"].between(1, 5).all()


def test_genuine_products_are_rarely_flagged(products):
    assert flag_rate(products, "genuine_j") == 0
    assert flag_rate(products, "genuine_divisive") <= 0.1


@pytest.mark.parametrize("pattern", ["bimodal_attack", "positive_stuffing", "burst_campaign"])
def test_manipulated_products_are_mostly_flagged(products, pattern):
    assert flag_rate(products, pattern) >= 0.8


def test_bimodal_attack_has_high_bsi_and_stuffing_does_not(products):
    by = products.groupby("pattern")["bsi"].median()
    assert by["bimodal_attack"] > 0.3
    assert by["positive_stuffing"] < 0.1


def test_every_flag_has_a_reason(products):
    flagged = products[products["flag"]]
    assert (flagged["reason_1"] != "").all()
