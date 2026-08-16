from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class ScoringWeightsConfig(Base):
    """Versioned BTC investment score weights. A new row is inserted whenever weights change
    (never mutated in place) so that every historical ScoreHistory row stays traceable to the
    exact weights that produced it. Exactly one row has is_active=True at a time; the app-level
    invariant "weights sum to 1.0" is enforced in the service layer on write, not via a
    dialect-specific CHECK constraint."""

    __tablename__ = "scoring_weights_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer)
    valuation_weight: Mapped[float] = mapped_column(Numeric(4, 3))
    sentiment_weight: Mapped[float] = mapped_column(Numeric(4, 3))
    cycle_weight: Mapped[float] = mapped_column(Numeric(4, 3))
    macro_weight: Mapped[float] = mapped_column(Numeric(4, 3))
    momentum_weight: Mapped[float] = mapped_column(Numeric(4, 3))
    onchain_weight: Mapped[float] = mapped_column(Numeric(4, 3))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
