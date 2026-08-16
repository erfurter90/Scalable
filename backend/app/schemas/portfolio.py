from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class AllocationItem(BaseModel):
    subcategory: str
    amount: Decimal
    percent_of_total: float


class PortfolioAllocationOut(BaseModel):
    snapshot_date: date
    total_assets: Decimal
    breakdown: list[AllocationItem]
    btc_percent_of_assets: float
    btc_percent_of_investments: float


class CryptoAllocationItem(BaseModel):
    # The CoinGecko coin id (e.g. "solana") when the entry was quantity-tracked, otherwise
    # the entry's own label — coins without a known id can't be merged across entries, so
    # each such entry stays its own slice.
    coin: str
    amount: Decimal
    percent_of_crypto: float


class CryptoBreakdownOut(BaseModel):
    """Breaks the "andere Krypto" (crypto) subcategory of the main portfolio allocation down
    further, per individual coin — useful since the mix within that bucket can shift much
    faster than the broad cash/BTC/crypto/stocks/etf/other split."""

    snapshot_date: date
    total_crypto: Decimal
    breakdown: list[CryptoAllocationItem]
