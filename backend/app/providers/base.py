"""The one contract every external data source must satisfy. `market_data_service` only
ever talks to providers through this interface — it never calls httpx/requests itself.

A provider must NEVER raise out of `fetch()`. Network errors, timeouts, missing API keys,
or fields CoinGecko/etc. simply don't return: all of these come back as a ProviderResult
with status="error" or "unavailable" so the caller can persist an honest audit trail
instead of crashing or silently fabricating a number.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol

ProviderStatus = Literal["ok", "unavailable", "error"]


@dataclass
class ProviderResult:
    metric: str
    value: Decimal | None
    raw: dict | None
    unit: str | None
    status: ProviderStatus
    source: str
    source_endpoint: str | None
    as_of: datetime | None
    error_message: str | None = None


class MarketDataProvider(Protocol):
    name: str

    def fetch(self, metric: str) -> ProviderResult:
        """Fetch a single metric. Returns status="unavailable" if this provider doesn't
        know the metric at all, or status="error" if it knows it but the call failed."""
        ...

    def supported_metrics(self) -> list[str]: ...
