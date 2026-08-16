from decimal import Decimal

import httpx

from app.providers.feargreed_provider import AlternativeMeFearGreedProvider

FIXTURE_RESPONSE = {
    "data": [
        {"value": "27", "value_classification": "Fear", "timestamp": "1755331200"},
    ]
}


def test_fetch_fear_greed_ok(monkeypatch):
    def _mock_get(url, params=None, timeout=None):
        request = httpx.Request("GET", url)
        return httpx.Response(200, json=FIXTURE_RESPONSE, request=request)

    monkeypatch.setattr(httpx, "get", _mock_get)
    provider = AlternativeMeFearGreedProvider()

    result = provider.fetch("fear_greed_index")

    assert result.status == "ok"
    assert result.value == Decimal(27)
    assert result.unit == "index_0_100"
    assert result.as_of is not None


def test_fetch_unsupported_metric_is_unavailable():
    provider = AlternativeMeFearGreedProvider()

    result = provider.fetch("btc_price_usd")

    assert result.status == "unavailable"


def test_fetch_empty_data_is_unavailable(monkeypatch):
    def _mock_get(url, params=None, timeout=None):
        request = httpx.Request("GET", url)
        return httpx.Response(200, json={"data": []}, request=request)

    monkeypatch.setattr(httpx, "get", _mock_get)
    provider = AlternativeMeFearGreedProvider()

    result = provider.fetch("fear_greed_index")

    assert result.status == "unavailable"


def test_fetch_network_error_is_error_status(monkeypatch):
    def _raising_get(url, params=None, timeout=None):
        raise httpx.ConnectTimeout("timed out")

    monkeypatch.setattr(httpx, "get", _raising_get)
    provider = AlternativeMeFearGreedProvider()

    result = provider.fetch("fear_greed_index")

    assert result.status == "error"
