import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class DataPointStatus(enum.StrEnum):
    ok = "ok"
    unavailable = "unavailable"
    error = "error"


class MarketDataPoint(Base):
    """Generic timestamped + sourced record for ANY external data point (BTC price,
    Fear & Greed, future macro metrics, ...). Every external fetch — success or failure —
    is persisted here, so the DB itself is the audit trail and nothing is ever fabricated:
    a failed/unconfigured fetch is recorded with status=unavailable/error, never silently
    dropped or replaced with a guess."""

    __tablename__ = "market_data_points"
    __table_args__ = (
        Index("ix_market_data_metric_fetched_at", "metric", "fetched_at"),
        Index("ix_market_data_metric_status", "metric", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    metric: Mapped[str] = mapped_column(String(64))  # e.g. "btc_price_usd", "fear_greed_index"
    value: Mapped[float | None] = mapped_column(Numeric(30, 10), nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # full provider payload
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)  # "usd", "index_0_100", ...
    source: Mapped[str] = mapped_column(String(64))  # "coingecko", "alternative_me", "mock"
    source_endpoint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[DataPointStatus] = mapped_column(Enum(DataPointStatus, native_enum=False, length=16))
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    as_of: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # timestamp the provider claims
