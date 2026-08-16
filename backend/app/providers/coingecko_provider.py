"""BTC price/market data from CoinGecko's free, keyless public API."""

import time
from datetime import UTC, datetime
from decimal import Decimal

import httpx

from app.providers.base import ProviderResult

_ENDPOINT = "https://api.coingecko.com/api/v3/coins/bitcoin"
_ENDPOINT_PARAMS = {
    "localization": "false",
    "tickers": "false",
    "market_data": "true",
    "community_data": "false",
    "developer_data": "false",
    "sparkline": "false",
}

# Maps our internal metric names to the (nested) field(s) in CoinGecko's response.
_METRIC_FIELDS = {
    "btc_price_usd": (("market_data", "current_price", "usd"), "usd"),
    "btc_price_eur": (("market_data", "current_price", "eur"), "eur"),
    "btc_change_24h": (("market_data", "price_change_percentage_24h"), "percent"),
    "btc_change_7d": (("market_data", "price_change_percentage_7d"), "percent"),
    "btc_change_30d": (("market_data", "price_change_percentage_30d"), "percent"),
    "btc_market_cap_usd": (("market_data", "market_cap", "usd"), "usd"),
    "btc_volume_usd_24h": (("market_data", "total_volume", "usd"), "usd"),
}

_SIMPLE_PRICE_ENDPOINT = "https://api.coingecko.com/api/v3/simple/price"
_CACHE_TTL_SECONDS = 30


class CoinGeckoProvider:
    """A single dashboard load asks for ~5 BTC metrics; rather than firing 5 near-identical
    HTTP requests, the one underlying API response is cached in-memory for a short TTL and
    reused across fetch() calls for different metrics within that window."""

    name = "coingecko"

    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self._timeout = timeout_seconds
        self._cached_response: dict | None = None
        self._cached_at: float = 0.0

    def supported_metrics(self) -> list[str]:
        return list(_METRIC_FIELDS.keys())

    def fetch(self, metric: str) -> ProviderResult:
        if metric not in _METRIC_FIELDS:
            return ProviderResult(
                metric=metric,
                value=None,
                raw=None,
                unit=None,
                status="unavailable",
                source=self.name,
                source_endpoint=_ENDPOINT,
                as_of=None,
                error_message="metric not supported by CoinGeckoProvider",
            )

        try:
            data = self._get_market_data()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            return ProviderResult(
                metric=metric,
                value=None,
                raw=None,
                unit=None,
                status="error",
                source=self.name,
                source_endpoint=_ENDPOINT,
                as_of=None,
                error_message=str(exc),
            )

        path, unit = _METRIC_FIELDS[metric]
        value = _dig(data, path)
        if value is None:
            return ProviderResult(
                metric=metric,
                value=None,
                raw=data,
                unit=unit,
                status="unavailable",
                source=self.name,
                source_endpoint=_ENDPOINT,
                as_of=None,
                error_message="field missing from CoinGecko response",
            )

        as_of = _parse_last_updated(data)
        return ProviderResult(
            metric=metric,
            value=Decimal(str(value)),
            raw=data,
            unit=unit,
            status="ok",
            source=self.name,
            source_endpoint=_ENDPOINT,
            as_of=as_of,
        )

    def _get_market_data(self) -> dict:
        now = time.monotonic()
        if self._cached_response is not None and (now - self._cached_at) < _CACHE_TTL_SECONDS:
            return self._cached_response

        response = httpx.get(_ENDPOINT, params=_ENDPOINT_PARAMS, timeout=self._timeout)
        response.raise_for_status()
        data = response.json()
        self._cached_response = data
        self._cached_at = now
        return data

    def fetch_price(self, coin_id: str, vs_currency: str) -> ProviderResult:
        """Fetches the current price of an arbitrary CoinGecko coin (used for quantity-based
        financial entries, e.g. "0.2 BTC" or "3 ETH" — priced on demand, not part of the fixed
        `_METRIC_FIELDS` set above since the coin is chosen per entry, not known in advance."""
        metric = f"crypto_price_{coin_id}_{vs_currency}"
        try:
            response = httpx.get(
                _SIMPLE_PRICE_ENDPOINT,
                params={"ids": coin_id, "vs_currencies": vs_currency},
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            return ProviderResult(
                metric=metric,
                value=None,
                raw=None,
                unit=vs_currency,
                status="error",
                source=self.name,
                source_endpoint=_SIMPLE_PRICE_ENDPOINT,
                as_of=None,
                error_message=str(exc),
            )

        price = data.get(coin_id, {}).get(vs_currency)
        if price is None:
            return ProviderResult(
                metric=metric,
                value=None,
                raw=data,
                unit=vs_currency,
                status="unavailable",
                source=self.name,
                source_endpoint=_SIMPLE_PRICE_ENDPOINT,
                as_of=None,
                error_message=f"CoinGecko has no price for coin id '{coin_id}' in '{vs_currency}'",
            )

        return ProviderResult(
            metric=metric,
            value=Decimal(str(price)),
            raw=data,
            unit=vs_currency,
            status="ok",
            source=self.name,
            source_endpoint=_SIMPLE_PRICE_ENDPOINT,
            as_of=datetime.now(UTC),
        )


def _dig(data: dict, path: tuple[str, ...]) -> float | None:
    current: object = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current if isinstance(current, int | float) else None


def _parse_last_updated(data: dict) -> datetime | None:
    raw = data.get("last_updated")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw).astimezone(UTC)
    except ValueError:
        return None
