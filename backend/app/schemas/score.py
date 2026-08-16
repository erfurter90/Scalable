from datetime import date

from pydantic import BaseModel


class SubScoreOut(BaseModel):
    name: str
    value: float | None
    status: str
    unavailable_reason: str | None
    inputs: dict
    weight_declared: float  # the configured weight, before renormalization
    weight_used: float | None  # renormalized weight actually applied; None if unavailable


class ScoreOut(BaseModel):
    score_date: date
    total_score: float | None
    weights_config_version: int
    subscores: list[SubScoreOut]
