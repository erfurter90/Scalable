from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class ScoreHistory(Base):
    """One computed BTC investment score per day. subscores_json and inputs_json capture the
    full breakdown (which sub-scores were available, their raw inputs) so every score is
    explainable after the fact, not just a bare number."""

    __tablename__ = "score_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    score_date: Mapped[date] = mapped_column(Date, index=True)
    total_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)  # None if nothing available
    subscores_json: Mapped[dict] = mapped_column(JSON)  # {"sentiment": {"value": 62, "status": "ok"}, ...}
    weights_config_id: Mapped[int] = mapped_column(ForeignKey("scoring_weights_configs.id"))
    inputs_json: Mapped[dict] = mapped_column(JSON)  # raw values used (fear_greed value, price change %, ...)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
