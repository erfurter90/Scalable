from dataclasses import dataclass

import pytest

from app.scoring.engine import SubScoreResult, combine_subscores, renormalize_weights


@dataclass
class FakeWeights:
    valuation_weight: float = 0.25
    sentiment_weight: float = 0.20
    cycle_weight: float = 0.20
    macro_weight: float = 0.15
    momentum_weight: float = 0.10
    onchain_weight: float = 0.10


def _all_available_subscores() -> list[SubScoreResult]:
    return [
        SubScoreResult(name="valuation", value=80.0, status="ok"),
        SubScoreResult(name="sentiment", value=40.0, status="ok"),
        SubScoreResult(name="cycle", value=60.0, status="ok"),
        SubScoreResult(name="macro", value=50.0, status="ok"),
        SubScoreResult(name="momentum", value=70.0, status="ok"),
        SubScoreResult(name="onchain", value=30.0, status="ok"),
    ]


def test_combine_all_available_matches_weighted_average():
    result = combine_subscores(_all_available_subscores(), FakeWeights())

    expected = 80.0 * 0.25 + 40.0 * 0.20 + 60.0 * 0.20 + 50.0 * 0.15 + 70.0 * 0.10 + 30.0 * 0.10
    assert result.total_score == pytest.approx(expected, abs=0.01)
    assert result.weights_used == pytest.approx(
        {"valuation": 0.25, "sentiment": 0.20, "cycle": 0.20, "macro": 0.15, "momentum": 0.10, "onchain": 0.10}
    )


def test_combine_renormalizes_when_some_unavailable():
    # Mirrors the MVP reality: only sentiment/cycle/momentum are ever "ok".
    subscores = [
        SubScoreResult(name="valuation", value=None, status="unavailable", unavailable_reason="no data"),
        SubScoreResult(name="sentiment", value=60.0, status="ok"),
        SubScoreResult(name="cycle", value=80.0, status="ok"),
        SubScoreResult(name="macro", value=None, status="unavailable", unavailable_reason="no data"),
        SubScoreResult(name="momentum", value=40.0, status="ok"),
        SubScoreResult(name="onchain", value=None, status="unavailable", unavailable_reason="no data"),
    ]

    result = combine_subscores(subscores, FakeWeights())

    # available weights: sentiment .20 + cycle .20 + momentum .10 = .50 -> renormalized to sum 1.0
    assert result.weights_used["sentiment"] == pytest.approx(0.20 / 0.50)
    assert result.weights_used["cycle"] == pytest.approx(0.20 / 0.50)
    assert result.weights_used["momentum"] == pytest.approx(0.10 / 0.50)
    assert "valuation" not in result.weights_used

    expected = 60.0 * (0.20 / 0.50) + 80.0 * (0.20 / 0.50) + 40.0 * (0.10 / 0.50)
    assert result.total_score == pytest.approx(expected, abs=0.01)


def test_combine_all_unavailable_returns_none_score():
    subscores = [
        SubScoreResult(name=name, value=None, status="unavailable", unavailable_reason="no data")
        for name in ["valuation", "sentiment", "cycle", "macro", "momentum", "onchain"]
    ]

    result = combine_subscores(subscores, FakeWeights())

    assert result.total_score is None
    assert result.weights_used == {}


def test_combine_rejects_weights_not_summing_to_one():
    bad_weights = FakeWeights(valuation_weight=0.5)  # now sums to 1.25

    with pytest.raises(ValueError, match="sum to 1.0"):
        combine_subscores(_all_available_subscores(), bad_weights)


def test_combine_clamps_to_0_100():
    # A pathological sub-score value outside 0-100 should not blow up the total past bounds.
    subscores = _all_available_subscores()
    subscores[0].value = 500.0  # valuation absurdly high

    result = combine_subscores(subscores, FakeWeights())

    assert 0.0 <= result.total_score <= 100.0


def test_renormalize_weights_empty_available_returns_empty():
    assert renormalize_weights({"a": 0.5, "b": 0.5}, set()) == {}


def test_renormalize_weights_single_available_gets_full_weight():
    result = renormalize_weights({"a": 0.3, "b": 0.7}, {"a"})
    assert result == {"a": 1.0}
