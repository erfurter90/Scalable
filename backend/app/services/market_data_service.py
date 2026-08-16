"""Fetches metrics through the provider registry and persists every attempt — success or
failure — as a MarketDataPoint row. This is the only layer that touches providers/; routers
never call a provider directly.

A short DB-backed freshness TTL avoids hammering free public APIs (CoinGecko, alternative.me)
on every dashboard load: if the latest stored point for a metric is recent and status="ok",
it's reused instead of re-fetching.
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.market_data import DataPointStatus, MarketDataPoint
from app.providers.registry import get_provider_for_metric
from app.schemas.market_data import (
    BtcPriceOut,
    FearGreedOut,
    MarketDataPointOut,
    MarketSnapshotOut,
)

FRESHNESS_TTL_SECONDS = 300  # 5 minutes


def get_latest(db: Session, metric: str) -> MarketDataPoint | None:
    return (
        db.query(MarketDataPoint)
        .filter(MarketDataPoint.metric == metric)
        .order_by(MarketDataPoint.fetched_at.desc())
        .first()
    )


def _fetch_and_store(db: Session, metric: str) -> MarketDataPoint:
    provider = get_provider_for_metric(metric)

    if provider is None:
        point = MarketDataPoint(
            metric=metric,
            value=None,
            raw_json=None,
            unit=None,
            source="none",
            source_endpoint=None,
            status=DataPointStatus.unavailable,
            error_message="no provider configured for this metric",
            as_of=None,
        )
    else:
        result = provider.fetch(metric)
        point = MarketDataPoint(
            metric=metric,
            value=result.value,
            raw_json=result.raw,
            unit=result.unit,
            source=result.source,
            source_endpoint=result.source_endpoint,
            status=DataPointStatus(result.status),
            error_message=result.error_message,
            # DB DateTime columns are naive-UTC (matches server_default=func.now()); strip
            # tzinfo here rather than storing timezone-aware values that would compare
            # inconsistently with fetched_at.
            as_of=result.as_of.replace(tzinfo=None) if result.as_of else None,
        )

    db.add(point)
    db.commit()
    db.refresh(point)
    return point


def get_fresh(db: Session, metric: str, max_age_seconds: int = FRESHNESS_TTL_SECONDS) -> MarketDataPoint:
    latest = get_latest(db, metric)
    if latest is not None and latest.status == DataPointStatus.ok:
        age_seconds = (datetime.now(UTC).replace(tzinfo=None) - latest.fetched_at).total_seconds()
        if age_seconds < max_age_seconds:
            return latest
    return _fetch_and_store(db, metric)


def _to_out(point: MarketDataPoint) -> MarketDataPointOut:
    return MarketDataPointOut.model_validate(point)


def get_btc_price(db: Session) -> BtcPriceOut:
    return BtcPriceOut(
        usd=_to_out(get_fresh(db, "btc_price_usd")),
        eur=_to_out(get_fresh(db, "btc_price_eur")),
        change_24h=_to_out(get_fresh(db, "btc_change_24h")),
        change_7d=_to_out(get_fresh(db, "btc_change_7d")),
        change_30d=_to_out(get_fresh(db, "btc_change_30d")),
    )


def get_fear_greed(db: Session) -> FearGreedOut:
    return FearGreedOut(index=_to_out(get_fresh(db, "fear_greed_index")))


def get_snapshot(db: Session) -> MarketSnapshotOut:
    return MarketSnapshotOut(btc=get_btc_price(db), fear_greed=get_fear_greed(db))
