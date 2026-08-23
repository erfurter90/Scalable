from datetime import datetime

from pydantic import BaseModel


class MarketDataPointOut(BaseModel):
    metric: str
    value: float | None
    unit: str | None
    status: str
    source: str
    source_endpoint: str | None
    fetched_at: datetime
    as_of: datetime | None
    error_message: str | None

    model_config = {"from_attributes": True}


class BtcPriceOut(BaseModel):
    usd: MarketDataPointOut
    eur: MarketDataPointOut
    change_24h: MarketDataPointOut
    change_7d: MarketDataPointOut
    change_30d: MarketDataPointOut


class FearGreedOut(BaseModel):
    index: MarketDataPointOut


class BtcDominanceOut(BaseModel):
    dominance: MarketDataPointOut


class MarketSnapshotOut(BaseModel):
    btc: BtcPriceOut
    fear_greed: FearGreedOut
    btc_dominance: BtcDominanceOut
