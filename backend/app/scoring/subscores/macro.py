"""Macro sub-score: unavailable in the MVP. Real macro data (rates, inflation, DXY, ...)
needs a keyed API (e.g. FRED) not yet configured. See providers/ for how to add one later —
the moment a MacroProvider exists, this module gains a real computation."""

from app.scoring.engine import SubScoreResult


def compute() -> SubScoreResult:
    return SubScoreResult(
        name="macro",
        value=None,
        status="unavailable",
        unavailable_reason="Requires a macro data API (e.g. FRED) with an API key; not configured in the MVP.",
    )
