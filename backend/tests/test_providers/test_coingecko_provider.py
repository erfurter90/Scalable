from decimal import Decimal

import httpx

from app.providers.coingecko_provider import CoinGeckoProvider

FIXTURE_RESPONSE = {
    "last_updated": "2026-08-16T10:00:00.000Z",
    "market_data": {
        "current_price": {"usd": 65000.0, "eur": 60000.0},
        "price_change_percentage_24h": 1.5,
        "price_change_percentage_7d": -2.3,
        "price_change_percentage_30d": 10.0,
        "market_cap": {"usd": 1280000000000},
        "total_volume": {"usd": 32000000000},
    },
}


def _mock_get_factory(json_body: dict, status_code: int = 200):
    def _mock_get(url, params=None, timeout=None):
        request = httpx.Request("GET", url)
        return httpx.Response(status_code, json=json_body, request=request)

    return _mock_get


def test_fetch_btc_price_usd_ok(monkeypatch):
    monkeypatch.setattr(httpx, "get", _mock_get_factory(FIXTURE_RESPONSE))
    provider = CoinGeckoProvider()

    result = provider.fetch("btc_price_usd")

    assert result.status == "ok"
    assert result.value == Decimal("65000.0")
    assert result.unit == "usd"
    assert result.source == "coingecko"
    assert result.as_of is not None


def test_fetch_caches_across_metrics(monkeypatch):
    call_count = {"n": 0}

    def _counting_get(url, params=None, timeout=None):
        call_count["n"] += 1
        request = httpx.Request("GET", url)
        return httpx.Response(200, json=FIXTURE_RESPONSE, request=request)

    monkeypatch.setattr(httpx, "get", _counting_get)
    provider = CoinGeckoProvider()

    provider.fetch("btc_price_usd")
    provider.fetch("btc_price_eur")
    provider.fetch("btc_change_24h")

    assert call_count["n"] == 1  # single underlying HTTP call, reused via short-lived cache


def test_fetch_unsupported_metric_is_unavailable():
    provider = CoinGeckoProvider()

    result = provider.fetch("something_unknown")

    assert result.status == "unavailable"
    assert result.value is None


def test_fetch_http_error_is_error_status(monkeypatch):
    def _raising_get(url, params=None, timeout=None):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "get", _raising_get)
    provider = CoinGeckoProvider()

    result = provider.fetch("btc_price_usd")

    assert result.status == "error"
    assert result.value is None
    assert "connection refused" in result.error_message


def test_fetch_missing_field_is_unavailable(monkeypatch):
    incomplete_response = {"last_updated": "2026-08-16T10:00:00.000Z", "market_data": {}}
    monkeypatch.setattr(httpx, "get", _mock_get_factory(incomplete_response))
    provider = CoinGeckoProvider()

    result = provider.fetch("btc_price_usd")

    assert result.status == "unavailable"


def test_fetch_price_ok(monkeypatch):
    monkeypatch.setattr(httpx, "get", _mock_get_factory({"ethereum": {"eur": 3000.5}}))
    provider = CoinGeckoProvider()

    result = provider.fetch_price("ethereum", "eur")

    assert result.status == "ok"
    assert result.value == Decimal("3000.5")
    assert result.unit == "eur"
    assert result.metric == "crypto_price_ethereum_eur"


def test_fetch_price_unknown_coin_is_unavailable(monkeypatch):
    monkeypatch.setattr(httpx, "get", _mock_get_factory({}))
    provider = CoinGeckoProvider()

    result = provider.fetch_price("not-a-real-coin", "eur")

    assert result.status == "unavailable"
    assert result.value is None


def test_fetch_price_http_error_is_error_status(monkeypatch):
    def _raising_get(url, params=None, timeout=None):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "get", _raising_get)
    provider = CoinGeckoProvider()

    result = provider.fetch_price("bitcoin", "eur")

    assert result.status == "error"
