"""Momentum sub-score: derived from BTC's 7d and 30d price change, mapped onto a 0-100 scale
centered at 50 (= no momentum either way). The 30d change is weighted more heavily (60/40)
since it's less noisy than the 7d figure. Coefficients are simple and fixed here rather than
DB-configurable — unlike the top-level category weights, these aren't a value judgement the
spec asks to be tunable, just a smoothing choice."""

from app.scoring.engine import SubScoreResult

_WEIGHT_30D = 0.6
_WEIGHT_7D = 0.4


def compute(change_7d_pct: float | None, change_30d_pct: float | None) -> SubScoreResult:
    if change_7d_pct is None or change_30d_pct is None:
        return SubScoreResult(
            name="momentum",
            value=None,
            status="unavailable",
            unavailable_reason="BTC 7d/30d price change not available",
        )

    raw = 50.0 + _WEIGHT_30D * float(change_30d_pct) + _WEIGHT_7D * float(change_7d_pct)
    value = max(0.0, min(100.0, raw))
    return SubScoreResult(
        name="momentum",
        value=value,
        status="ok",
        inputs={"change_7d_pct": float(change_7d_pct), "change_30d_pct": float(change_30d_pct)},
    )
