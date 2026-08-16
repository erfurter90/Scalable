"""Deterministic stand-in used in tests and whenever MARKET_DATA_MODE=mock (e.g. offline
dev). Never used silently in a "live" configuration — see registry.py: a live provider that
fails returns status=unavailable/error, it is never swapped for mock data behind the scenes,
since that would violate the "never fabricate" rule."""

from datetime import UTC, datetime
from decimal import Decimal

from app.providers.base import ProviderResult

_FIXED_VALUES: dict[str, tuple[Decimal, str]] = {
    "btc_price_usd": (Decimal("65000.00"), "usd"),
    "btc_price_eur": (Decimal("60000.00"), "eur"),
    "btc_change_24h": (Decimal("1.25"), "percent"),
    "btc_change_7d": (Decimal("-3.40"), "percent"),
    "btc_change_30d": (Decimal("8.10"), "percent"),
    "btc_market_cap_usd": (Decimal(1280000000000), "usd"),
    "btc_volume_usd_24h": (Decimal(32000000000), "usd"),
    "fear_greed_index": (Decimal(50), "index_0_100"),
    "fx_usd_eur": (Decimal("0.92"), "EUR"),
}

# Deterministic per-coin prices for quantity-based valuation, keyed by (coin_id, vs_currency).
_MOCK_COIN_PRICES: dict[tuple[str, str], Decimal] = {
    ("bitcoin", "eur"): Decimal("60000.00"),
    ("bitcoin", "usd"): Decimal("65000.00"),
    ("ethereum", "eur"): Decimal("3000.00"),
    ("ethereum", "usd"): Decimal("3250.00"),
}


class MockProvider:
    name = "mock"

    def supported_metrics(self) -> list[str]:
        return list(_FIXED_VALUES.keys())

    def fetch(self, metric: str) -> ProviderResult:
        if metric not in _FIXED_VALUES:
            return ProviderResult(
                metric=metric,
                value=None,
                raw=None,
                unit=None,
                status="unavailable",
                source=self.name,
                source_endpoint=None,
                as_of=None,
                error_message="metric not supported by MockProvider",
            )

        value, unit = _FIXED_VALUES[metric]
        return ProviderResult(
            metric=metric,
            value=value,
            raw={"mock": True},
            unit=unit,
            status="ok",
            source=self.name,
            source_endpoint=None,
            as_of=datetime.now(UTC),
        )

    def fetch_price(self, coin_id: str, vs_currency: str) -> ProviderResult:
        metric = f"crypto_price_{coin_id}_{vs_currency}"
        price = _MOCK_COIN_PRICES.get((coin_id, vs_currency))
        if price is None:
            return ProviderResult(
                metric=metric,
                value=None,
                raw=None,
                unit=vs_currency,
                status="unavailable",
                source=self.name,
                source_endpoint=None,
                as_of=None,
                error_message=f"no mock price configured for coin id '{coin_id}'",
            )

        return ProviderResult(
            metric=metric,
            value=price,
            raw={"mock": True},
            unit=vs_currency,
            status="ok",
            source=self.name,
            source_endpoint=None,
            as_of=datetime.now(UTC),
        )
