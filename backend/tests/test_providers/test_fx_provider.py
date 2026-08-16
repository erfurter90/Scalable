from decimal import Decimal

import httpx

from app.providers.fx_provider import FrankfurterFxProvider


def test_fetch_usd_eur_rate_ok(monkeypatch):
    def _mock_get(url, params=None, timeout=None, follow_redirects=None):
        request = httpx.Request("GET", url)
        return httpx.Response(200, json={"amount": 1.0, "base": "USD", "rates": {"EUR": 0.92}}, request=request)

    monkeypatch.setattr(httpx, "get", _mock_get)
    provider = FrankfurterFxProvider()

    result = provider.fetch("fx_usd_eur")

    assert result.status == "ok"
    assert result.value == Decimal("0.92")
    assert result.unit == "EUR"


def test_fetch_unsupported_metric_is_unavailable():
    provider = FrankfurterFxProvider()

    result = provider.fetch("fx_eur_gbp")

    assert result.status == "unavailable"


def test_fetch_missing_rate_is_unavailable(monkeypatch):
    def _mock_get(url, params=None, timeout=None, follow_redirects=None):
        request = httpx.Request("GET", url)
        return httpx.Response(200, json={"amount": 1.0, "base": "USD", "rates": {}}, request=request)

    monkeypatch.setattr(httpx, "get", _mock_get)
    provider = FrankfurterFxProvider()

    result = provider.fetch("fx_usd_eur")

    assert result.status == "unavailable"


def test_fetch_network_error_is_error_status(monkeypatch):
    def _raising_get(url, params=None, timeout=None, follow_redirects=None):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "get", _raising_get)
    provider = FrankfurterFxProvider()

    result = provider.fetch("fx_usd_eur")

    assert result.status == "error"
