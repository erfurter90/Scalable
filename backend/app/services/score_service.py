"""Orchestrates the deterministic BTC investment score: pulls fresh market data (through
market_data_service, never directly from a provider), runs every sub-score module, combines
them via scoring/engine.py, and persists the full breakdown to ScoreHistory. Nothing in this
module calls an LLM — this is the "compute" half of the compute-then-phrase split.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.models.market_data import DataPointStatus, MarketDataPoint
from app.models.score_history import ScoreHistory
from app.models.scoring_config import ScoringWeightsConfig
from app.schemas.score import ScoreOut, SubScoreOut
from app.scoring.engine import (
    WEIGHT_FIELD_MAP,
    ScoreResult,
    combine_subscores,
    renormalize_weights,
)
from app.scoring.subscores import cycle, macro, momentum, onchain, sentiment, valuation
from app.services import market_data_service


def get_active_weights(db: Session) -> ScoringWeightsConfig:
    weights = (
        db.query(ScoringWeightsConfig)
        .filter(ScoringWeightsConfig.is_active.is_(True))
        .order_by(ScoringWeightsConfig.version.desc())
        .first()
    )
    if weights is None:
        raise RuntimeError("No active ScoringWeightsConfig found — has the seed migration run?")
    return weights


def _metric_value(point: MarketDataPoint) -> float | None:
    if point.status != DataPointStatus.ok or point.value is None:
        return None
    return float(point.value)


def compute_current_score(db: Session) -> tuple[ScoreResult, ScoringWeightsConfig]:
    fear_greed_point = market_data_service.get_fresh(db, "fear_greed_index")
    change_7d_point = market_data_service.get_fresh(db, "btc_change_7d")
    change_30d_point = market_data_service.get_fresh(db, "btc_change_30d")

    subscores = [
        sentiment.compute(_metric_value(fear_greed_point)),
        momentum.compute(_metric_value(change_7d_point), _metric_value(change_30d_point)),
        cycle.compute(),
        valuation.compute(),
        macro.compute(),
        onchain.compute(),
    ]

    weights = get_active_weights(db)
    result = combine_subscores(subscores, weights)
    return result, weights


def compute_and_store_score(
    db: Session, score_date: date | None = None
) -> tuple[ScoreHistory, ScoreResult, ScoringWeightsConfig]:
    score_date = score_date or date.today()
    result, weights = compute_current_score(db)

    subscores_json = {
        name: {"value": s.value, "status": s.status, "unavailable_reason": s.unavailable_reason}
        for name, s in result.subscores.items()
    }
    inputs_json = {name: s.inputs for name, s in result.subscores.items()}

    row = db.query(ScoreHistory).filter(ScoreHistory.score_date == score_date).first()
    if row is None:
        row = ScoreHistory(score_date=score_date)
        db.add(row)

    row.total_score = result.total_score
    row.subscores_json = subscores_json
    row.weights_config_id = weights.id
    row.inputs_json = inputs_json

    db.commit()
    db.refresh(row)
    return row, result, weights


def get_history(db: Session, date_from: date | None = None, date_to: date | None = None) -> list[ScoreHistory]:
    query = db.query(ScoreHistory)
    if date_from is not None:
        query = query.filter(ScoreHistory.score_date >= date_from)
    if date_to is not None:
        query = query.filter(ScoreHistory.score_date <= date_to)
    return query.order_by(ScoreHistory.score_date.asc()).all()


def history_row_to_score_out(db: Session, row: ScoreHistory) -> ScoreOut:
    """Reconstructs a ScoreOut from a persisted ScoreHistory row (used by /history, where we
    must not recompute against today's live market data — only replay what actually
    produced that historical score)."""
    weights = db.get(ScoringWeightsConfig, row.weights_config_id)
    weights_declared = {name: float(getattr(weights, field_name)) for name, field_name in WEIGHT_FIELD_MAP.items()}
    available_names = {name for name, s in row.subscores_json.items() if s["status"] == "ok"}
    weights_used = renormalize_weights(weights_declared, available_names)

    return ScoreOut(
        score_date=row.score_date,
        total_score=float(row.total_score) if row.total_score is not None else None,
        weights_config_version=weights.version,
        subscores=[
            SubScoreOut(
                name=name,
                value=s["value"],
                status=s["status"],
                unavailable_reason=s["unavailable_reason"],
                inputs=row.inputs_json.get(name, {}),
                weight_declared=weights_declared.get(name, 0.0),
                weight_used=weights_used.get(name),
            )
            for name, s in row.subscores_json.items()
        ],
    )


def to_score_out(result: ScoreResult, weights: ScoringWeightsConfig, score_date: date) -> ScoreOut:
    subscore_names = list(result.subscores.keys())
    return ScoreOut(
        score_date=score_date,
        total_score=result.total_score,
        weights_config_version=weights.version,
        subscores=[
            SubScoreOut(
                name=name,
                value=result.subscores[name].value,
                status=result.subscores[name].status,
                unavailable_reason=result.subscores[name].unavailable_reason,
                inputs=result.subscores[name].inputs,
                weight_declared=result.weights_declared.get(name, 0.0),
                weight_used=result.weights_used.get(name),
            )
            for name in subscore_names
        ],
    )
