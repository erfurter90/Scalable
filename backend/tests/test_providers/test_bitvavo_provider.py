import httpx

from app.core.config import get_settings
from app.providers.bitvavo_provider import BitvavoProvider, sign_for_test


def test_signature_matches_bitvavo_documented_example():
    # Real test vector from docs.bitvavo.com's authentication page, independently verified.
    signature = sign_for_test(
        timestamp="1548172481125",
        method="POST",
        path="/v2/order",
        body={"market": "BTC-EUR", "side": "buy", "price": "5000", "amount": "1.23", "orderType": "limit"},
        secret="bitvavo",
    )

    assert signature == "44d022723a20973a18f7ee97398b9fdd405d2d019c8d39e24b8cc0dcb39ca016"


def test_is_configured_false_without_key(monkeypatch):
    monkeypatch.setenv("BITVAVO_API_KEY", "")
    monkeypatch.setenv("BITVAVO_API_SECRET", "")
    get_settings.cache_clear()

    assert BitvavoProvider().is_configured is False

    get_settings.cache_clear()


def test_is_configured_true_with_key_and_secret(monkeypatch):
    monkeypatch.setenv("BITVAVO_API_KEY", "key123")
    monkeypatch.setenv("BITVAVO_API_SECRET", "secret456")
    get_settings.cache_clear()

    assert BitvavoProvider().is_configured is True

    get_settings.cache_clear()


def test_get_balance_not_configured_returns_error(monkeypatch):
    monkeypatch.setenv("BITVAVO_API_KEY", "")
    monkeypatch.setenv("BITVAVO_API_SECRET", "")
    get_settings.cache_clear()

    result = BitvavoProvider().get_balance()

    assert result.status == "error"
    assert result.data is None

    get_settings.cache_clear()


def test_get_balance_ok_sends_auth_headers_and_signs_correctly(monkeypatch):
    monkeypatch.setenv("BITVAVO_API_KEY", "key123")
    monkeypatch.setenv("BITVAVO_API_SECRET", "secret456")
    get_settings.cache_clear()

    captured = {}

    def _mock_get(url, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        request = httpx.Request("GET", url)
        return httpx.Response(200, json=[{"symbol": "BTC", "available": "0.5", "inOrder": "0"}], request=request)

    monkeypatch.setattr(httpx, "get", _mock_get)

    result = BitvavoProvider().get_balance()

    assert result.status == "ok"
    assert result.data == [{"symbol": "BTC", "available": "0.5", "inOrder": "0"}]
    assert captured["url"] == "https://api.bitvavo.com/v2/balance"
    assert captured["headers"]["Bitvavo-Access-Key"] == "key123"

    import hashlib
    import hmac

    expected_signature = hmac.new(
        b"secret456",
        f"{captured['headers']['Bitvavo-Access-Timestamp']}GET/v2/balance".encode(),
        hashlib.sha256,
    ).hexdigest()
    assert captured["headers"]["Bitvavo-Access-Signature"] == expected_signature

    get_settings.cache_clear()


def test_get_trades_builds_market_query_param(monkeypatch):
    monkeypatch.setenv("BITVAVO_API_KEY", "key123")
    monkeypatch.setenv("BITVAVO_API_SECRET", "secret456")
    get_settings.cache_clear()

    captured = {}

    def _mock_get(url, headers=None, timeout=None):
        captured["url"] = url
        request = httpx.Request("GET", url)
        return httpx.Response(200, json=[], request=request)

    monkeypatch.setattr(httpx, "get", _mock_get)

    BitvavoProvider().get_trades("SOL-EUR", limit=500)

    assert captured["url"] == "https://api.bitvavo.com/v2/trades?market=SOL-EUR&limit=500"

    get_settings.cache_clear()


def test_network_error_is_error_status_not_exception(monkeypatch):
    monkeypatch.setenv("BITVAVO_API_KEY", "key123")
    monkeypatch.setenv("BITVAVO_API_SECRET", "secret456")
    get_settings.cache_clear()

    def _raising_get(url, headers=None, timeout=None):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "get", _raising_get)

    result = BitvavoProvider().get_balance()

    assert result.status == "error"
    assert "connection refused" in result.error_message

    get_settings.cache_clear()
