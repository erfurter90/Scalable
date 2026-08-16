"""Maps a metric name to the provider instance responsible for it. This is the single
place that decides "live" vs "mock" mode (via MARKET_DATA_MODE) — services never
instantiate a provider directly."""

from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings
from app.providers.base import MarketDataProvider, ProviderResult
from app.providers.coingecko_provider import CoinGeckoProvider
from app.providers.feargreed_provider import AlternativeMeFearGreedProvider
from app.providers.fx_provider import FrankfurterFxProvider
from app.providers.mock_provider import MockProvider


class PriceProvider(Protocol):
    """Fetches the current price of an arbitrary coin — used for quantity-based financial
    entries (e.g. "0.2 BTC"), where the coin is chosen per entry rather than known upfront
    like the fixed dashboard metrics in MarketDataProvider."""

    def fetch_price(self, coin_id: str, vs_currency: str) -> ProviderResult: ...


@lru_cache
def _coingecko_provider() -> CoinGeckoProvider:
    return CoinGeckoProvider()


@lru_cache
def _mock_provider() -> MockProvider:
    return MockProvider()


@lru_cache
def _fx_provider() -> FrankfurterFxProvider:
    return FrankfurterFxProvider()


def _live_providers() -> list[MarketDataProvider]:
    return [_coingecko_provider(), AlternativeMeFearGreedProvider(), _fx_provider()]


def _mock_providers() -> list[MarketDataProvider]:
    return [_mock_provider()]


def get_price_provider() -> PriceProvider:
    settings = get_settings()
    return _mock_provider() if settings.market_data_mode == "mock" else _coingecko_provider()


def get_provider_for_metric(metric: str) -> MarketDataProvider | None:
    settings = get_settings()
    providers = _mock_providers() if settings.market_data_mode == "mock" else _live_providers()
    for provider in providers:
        if metric in provider.supported_metrics():
            return provider
    return None


def all_known_metrics() -> list[str]:
    settings = get_settings()
    providers = _mock_providers() if settings.market_data_mode == "mock" else _live_providers()
    metrics: list[str] = []
    for provider in providers:
        metrics.extend(provider.supported_metrics())
    return metrics
