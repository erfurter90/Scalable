"""On-chain sub-score: unavailable in the MVP. Reliable on-chain analytics (active
addresses, exchange flows, etc.) typically sit behind paid APIs; none is configured yet."""

from app.scoring.engine import SubScoreResult


def compute() -> SubScoreResult:
    return SubScoreResult(
        name="onchain",
        value=None,
        status="unavailable",
        unavailable_reason="Requires a paid on-chain analytics API; not available in the MVP.",
    )
