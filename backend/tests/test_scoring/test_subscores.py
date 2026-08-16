from datetime import date

import pytest

from app.scoring.subscores import cycle, macro, momentum, onchain, sentiment, valuation


class TestSentiment:
    def test_passes_through_value_directly(self):
        result = sentiment.compute(72.0)
        assert result.status == "ok"
        assert result.value == 72.0
        assert result.inputs == {"fear_greed_index": 72.0}

    def test_clamps_out_of_range_input(self):
        result = sentiment.compute(150.0)
        assert result.value == 100.0

    def test_none_input_is_unavailable(self):
        result = sentiment.compute(None)
        assert result.status == "unavailable"
        assert result.value is None
        assert result.unavailable_reason is not None


class TestMomentum:
    def test_zero_change_is_neutral_50(self):
        result = momentum.compute(change_7d_pct=0.0, change_30d_pct=0.0)
        assert result.value == 50.0

    def test_positive_change_raises_score_above_50(self):
        result = momentum.compute(change_7d_pct=10.0, change_30d_pct=10.0)
        assert result.value > 50.0

    def test_negative_change_lowers_score_below_50(self):
        result = momentum.compute(change_7d_pct=-10.0, change_30d_pct=-10.0)
        assert result.value < 50.0

    def test_clamps_extreme_positive_change(self):
        result = momentum.compute(change_7d_pct=500.0, change_30d_pct=500.0)
        assert result.value == 100.0

    def test_clamps_extreme_negative_change(self):
        result = momentum.compute(change_7d_pct=-500.0, change_30d_pct=-500.0)
        assert result.value == 0.0

    def test_missing_input_is_unavailable(self):
        result = momentum.compute(change_7d_pct=None, change_30d_pct=5.0)
        assert result.status == "unavailable"


class TestCycle:
    def test_right_after_halving_scores_near_100(self):
        result = cycle.compute(as_of=date(2024, 4, 21))  # 1 day after 2024-04-20 halving
        assert result.value == pytest.approx(100.0, abs=1.0)

    def test_right_before_next_halving_scores_near_0(self):
        # ~1 day before the estimated next halving (last + 1461 days)
        result = cycle.compute(as_of=date(2028, 4, 19))
        assert result.value < 5.0

    def test_always_available_no_api_needed(self):
        result = cycle.compute(as_of=date(2026, 8, 16))
        assert result.status == "ok"
        assert result.value is not None
        assert "last_halving_date" in result.inputs

    def test_picks_correct_halving_epoch(self):
        result = cycle.compute(as_of=date(2018, 1, 1))  # between 2016 and 2020 halvings
        assert result.inputs["last_halving_date"] == "2016-07-09"


class TestUnavailableStubs:
    def test_valuation_is_unavailable(self):
        result = valuation.compute()
        assert result.status == "unavailable"
        assert result.value is None
        assert result.unavailable_reason

    def test_macro_is_unavailable(self):
        result = macro.compute()
        assert result.status == "unavailable"

    def test_onchain_is_unavailable(self):
        result = onchain.compute()
        assert result.status == "unavailable"
