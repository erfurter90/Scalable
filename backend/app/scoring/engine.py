"""The deterministic core of the BTC investment score. This module — and only this module —
decides how sub-scores become the final 0-100 number. No LLM call happens anywhere in this
file or anything it imports; `services/score_service.py` calls this, persists the result,
and only *afterwards* may hand the already-computed numbers to the LLM for phrasing.
"""

from dataclasses import dataclass, field
from typing import Literal, Protocol

SubScoreStatus = Literal["ok", "unavailable"]

# Sub-score name -> the ScoringWeightsConfig field that holds its configured weight.
WEIGHT_FIELD_MAP: dict[str, str] = {
    "valuation": "valuation_weight",
    "sentiment": "sentiment_weight",
    "cycle": "cycle_weight",
    "macro": "macro_weight",
    "momentum": "momentum_weight",
    "onchain": "onchain_weight",
}


@dataclass
class SubScoreResult:
    name: str
    value: float | None  # 0-100, clamped; None if unavailable
    status: SubScoreStatus
    inputs: dict = field(default_factory=dict)  # raw values used, for explainability
    unavailable_reason: str | None = None


@dataclass
class ScoreResult:
    total_score: float | None  # None only if every sub-score is unavailable
    subscores: dict[str, SubScoreResult]
    weights_declared: dict[str, float]  # the configured weights, as stored
    weights_used: dict[str, float]  # renormalized weights actually applied (available sub-scores only)


class WeightsLike(Protocol):
    valuation_weight: float
    sentiment_weight: float
    cycle_weight: float
    macro_weight: float
    momentum_weight: float
    onchain_weight: float


def renormalize_weights(weights_declared: dict[str, float], available_names: set[str]) -> dict[str, float]:
    """Proportionally rescales the declared weights of `available_names` so they sum to 1.0.
    Shared by combine_subscores() (live computation) and score_service's history reconstruction
    (from persisted data), so both paths use identical renormalization math."""
    if not available_names:
        return {}
    available_weight_sum = sum(weights_declared[name] for name in available_names)
    return {name: weights_declared[name] / available_weight_sum for name in available_names}


def combine_subscores(subscores: list[SubScoreResult], weights: WeightsLike) -> ScoreResult:
    """Combines sub-scores into the final score. Unavailable sub-scores are excluded and the
    remaining weights are proportionally renormalized to still sum to 1.0 — documented here,
    not hidden — rather than silently treating a missing metric as 0 (which would understate
    the score) or leaving its weight unused (which would understate the total)."""

    subscores_by_name = {s.name: s for s in subscores}
    weights_declared = {name: float(getattr(weights, field_name)) for name, field_name in WEIGHT_FIELD_MAP.items()}

    declared_total = sum(weights_declared.values())
    if abs(declared_total - 1.0) > 1e-6:
        raise ValueError(f"Scoring weights must sum to 1.0, got {declared_total}")

    available_names = {
        name
        for name, result in subscores_by_name.items()
        if result.status == "ok" and result.value is not None and name in weights_declared
    }

    if not available_names:
        return ScoreResult(
            total_score=None,
            subscores=subscores_by_name,
            weights_declared=weights_declared,
            weights_used={},
        )

    weights_used = renormalize_weights(weights_declared, available_names)
    weighted_sum = sum(subscores_by_name[name].value * weights_used[name] for name in available_names)
    total_score = max(0.0, min(100.0, weighted_sum))

    return ScoreResult(
        total_score=round(total_score, 2),
        subscores=subscores_by_name,
        weights_declared=weights_declared,
        weights_used=weights_used,
    )
