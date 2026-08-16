"""Valuation sub-score: unavailable in the MVP. A reliable free MVRV (or similar on-chain
valuation) data source isn't wired up — per the hard rule "if a metric isn't reliably
available, mark it unavailable, never invent it", this returns status=unavailable rather
than a fabricated number. combine_subscores() renormalizes the remaining weights."""

from app.scoring.engine import SubScoreResult


def compute() -> SubScoreResult:
    return SubScoreResult(
        name="valuation",
        value=None,
        status="unavailable",
        unavailable_reason=(
            "Requires MVRV or similar on-chain valuation data; no reliable free source wired up yet."
        ),
    )
