"""Cycle sub-score: pure calendar math based on Bitcoin's known halving dates — no API
required, so this sub-score is always available.

Heuristic (documented, not a prediction): the score decays linearly from 100 right after a
halving to 0 right before the next one, reflecting the commonly observed historical pattern
of post-halving accumulation phases and pre-halving distribution/blow-off phases. This is a
simplification of "halving cycle theory", not a guarantee that past patterns repeat — the
raw inputs (dates, days) are exposed in full so the reasoning stays checkable.
"""

from datetime import date, timedelta

from app.scoring.engine import SubScoreResult

_HALVING_DATES = [
    date(2012, 11, 28),
    date(2016, 7, 9),
    date(2020, 5, 11),
    date(2024, 4, 20),
]
# Average interval between the historical halvings above (~4 years); used only to estimate
# the *next* halving date for cycle-position math, since the exact date depends on actual
# block production speed, which needs a live block-height API we don't have in the MVP.
_AVG_CYCLE_DAYS = 1461


def compute(as_of: date | None = None) -> SubScoreResult:
    as_of = as_of or date.today()
    last_halving = max(d for d in _HALVING_DATES if d <= as_of)
    estimated_next_halving = last_halving + timedelta(days=_AVG_CYCLE_DAYS)

    days_since_halving = (as_of - last_halving).days
    cycle_length_days = (estimated_next_halving - last_halving).days
    cycle_position = min(1.0, days_since_halving / cycle_length_days)

    value = max(0.0, min(100.0, 100.0 * (1 - cycle_position)))

    return SubScoreResult(
        name="cycle",
        value=value,
        status="ok",
        inputs={
            "last_halving_date": last_halving.isoformat(),
            "estimated_next_halving_date": estimated_next_halving.isoformat(),
            "days_since_last_halving": days_since_halving,
            "days_to_estimated_next_halving": (estimated_next_halving - as_of).days,
            "cycle_position_pct": round(cycle_position * 100, 1),
        },
    )
