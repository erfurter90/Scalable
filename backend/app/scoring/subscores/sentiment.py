"""Sentiment sub-score: a direct pass-through of the Crypto Fear & Greed Index (already a
0-100 scale). Deliberately NOT re-interpreted as a contrarian "buy the fear" signal here —
that would bake a market-timing assumption into the number itself. Any such interpretation
belongs in the LLM's plain-language explanation of the already-computed score, not in the
math that produces it."""

from app.scoring.engine import SubScoreResult


def compute(fear_greed_value: float | None) -> SubScoreResult:
    if fear_greed_value is None:
        return SubScoreResult(
            name="sentiment",
            value=None,
            status="unavailable",
            unavailable_reason="Fear & Greed Index not available",
        )

    value = max(0.0, min(100.0, float(fear_greed_value)))
    return SubScoreResult(
        name="sentiment",
        value=value,
        status="ok",
        inputs={"fear_greed_index": float(fear_greed_value)},
    )
