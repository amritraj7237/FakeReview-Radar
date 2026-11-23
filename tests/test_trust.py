import pytest

from analysis.radar.trust import band, combine, round_half_up, score, trust_score


def test_worked_example_from_trust_score_doc():
    # BSI 0.84, inflation 0, unverified 0.5, burst 0.6  ->  R = 0.76452, Trust 24
    risk = combine({"bsi": 0.84, "inflation": 0.0, "unverified": 0.5, "burst": 0.6})
    assert risk == pytest.approx(0.76452)
    assert trust_score(risk) == 24
    assert band(24) == "suspicious"


def test_bsi_alone_can_only_lower_trust_to_51():
    worst = combine({"bsi": 1.0, "inflation": 0.0, "unverified": 0.0, "burst": 0.0})
    assert trust_score(worst) == 51          # needs round-half-up: round(50.5) == 50 in Python
    assert band(51) == "mixed signals"


def test_round_half_up():
    assert round_half_up(50.5) == 51
    assert round(50.5) == 50


def test_skipping_a_signal_is_the_same_as_zero():
    with_zero = combine({"bsi": 0.3, "inflation": 0.0, "unverified": 0.4, "burst": 0.0})
    skipped = combine({"bsi": 0.3, "inflation": None, "unverified": 0.4, "burst": None})
    assert skipped == pytest.approx(with_zero)


def test_more_evidence_never_raises_trust():
    base = {"bsi": 0.2, "inflation": 0.1, "unverified": 0.0, "burst": 0.0}
    stronger = dict(base, burst=0.5)
    assert trust_score(combine(stronger)) <= trust_score(combine(base))


def test_perfect_burst_alone_is_suspicious_noisy_or_vs_weighted_average():
    risk = combine({"bsi": 0, "inflation": 0, "unverified": 0, "burst": 1})
    assert trust_score(risk) == 31
    weighted_average = 0.7 / (0.5 + 0.7 + 0.6 + 0.7)
    assert trust_score(weighted_average) == 72     # would wrongly look genuine


def test_bands_and_flag():
    assert [band(x) for x in (100, 66, 65, 45, 44, 1)] == [
        "looks genuine", "looks genuine", "mixed signals", "mixed signals", "suspicious", "suspicious"]
    assert score({"bsi": 0.0, "inflation": 0.0, "unverified": 0.0, "burst": 0.0})["flag"] is False
    result = score({"bsi": None, "inflation": None, "unverified": None, "burst": 1.0})
    assert result["flag"] is True
    assert result["not_measured"] == ["bsi", "inflation", "unverified"]
