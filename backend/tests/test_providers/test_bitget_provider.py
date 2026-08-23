import base64
import hashlib
import hmac

import httpx

from app.core.config import get_settings
from app.providers.bitget_provider import BitgetProvider, sign_for_test


def test_signature_matches_independently_computed_reference():
    # Reference value hand-computed outside the app (see PR description / commit) using the
    # exact algorithm documented in Bitget's official Python SDK
    # (BitgetLimited/v3-bitget-api-sdk, utils.py: sign()/pre_hash()) -- HMAC-SHA256, base64.
    signature = sign_for_test(
        timestamp="1700000000000",
        method="GET",
        request_path="/api/v2/spot/account/assets?coin=BTC&limit=100",
        body="",
        secret="my-test-secret",
    )

    assert signature == "18CCzUyDbp9XD4njS8UG6nSODhxSfiNEGxreoeS4JKY="


def test_is_configured_requires_all_three_credentials(monkeypatch):
    monkeypatch.setenv("BITGET_API_KEY", "key")
    monkeypatch.setenv("BITGET_API_SECRET", "secret")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "")
    get_settings.cache_clear()

    assert BitgetProvider().is_configured is False

    monkeypatch.setenv("BITGET_API_PASSPHRASE", "phrase")
    get_settings.cache_clear()

    assert BitgetProvider().is_configured is True

    get_settings.cache_clear()


def test_get_balance_not_configured_returns_error(monkeypatch):
    monkeypatch.setenv("BITGET_API_KEY", "")
    monkeypatch.setenv("BITGET_API_SECRET", "")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "")
    get_settings.cache_clear()

    result = BitgetProvider().get_balance()

    assert result.status == "error"
    assert result.data is None

    get_settings.cache_clear()


def test_get_balance_ok_sends_auth_headers_and_unwraps_envelope(monkeypatch):
    monkeypatch.setenv("BITGET_API_KEY", "key123")
    monkeypatch.setenv("BITGET_API_SECRET", "secret456")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "phrase789")
    get_settings.cache_clear()

    captured = {}

    def _mock_get(url, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        request = httpx.Request("GET", url)
        return httpx.Response(
            200,
            json={"code": "00000", "msg": "success", "data": [{"coin": "BTC", "available": "0.5"}]},
            request=request,
        )

    monkeypatch.setattr(httpx, "get", _mock_get)

    result = BitgetProvider().get_balance()

    assert result.status == "ok"
    assert result.data == [{"coin": "BTC", "available": "0.5"}]
    assert captured["url"] == "https://api.bitget.com/api/v2/spot/account/assets"
    assert captured["headers"]["ACCESS-KEY"] == "key123"
    assert captured["headers"]["ACCESS-PASSPHRASE"] == "phrase789"

    expected_signature = base64.b64encode(
        hmac.new(
            b"secret456",
            f"{captured['headers']['ACCESS-TIMESTAMP']}GET/api/v2/spot/account/assets".encode(),
            hashlib.sha256,
        ).digest()
    ).decode()
    assert captured["headers"]["ACCESS-SIGN"] == expected_signature

    get_settings.cache_clear()


def test_get_balance_business_error_code_is_error_status(monkeypatch):
    # Bitget returns HTTP 200 even for an invalid/unconfirmed key -- the failure shows up in
    # the `code` field, not the HTTP status.
    monkeypatch.setenv("BITGET_API_KEY", "key123")
    monkeypatch.setenv("BITGET_API_SECRET", "secret456")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "phrase789")
    get_settings.cache_clear()

    def _mock_get(url, headers=None, timeout=None):
        request = httpx.Request("GET", url)
        return httpx.Response(200, json={"code": "40037", "msg": "apikey not exist"}, request=request)

    monkeypatch.setattr(httpx, "get", _mock_get)

    result = BitgetProvider().get_balance()

    assert result.status == "error"
    assert "apikey not exist" in result.error_message

    get_settings.cache_clear()


def test_get_tax_spot_records_sorts_query_params_alphabetically(monkeypatch):
    monkeypatch.setenv("BITGET_API_KEY", "key123")
    monkeypatch.setenv("BITGET_API_SECRET", "secret456")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "phrase789")
    get_settings.cache_clear()

    captured = {}

    def _mock_get(url, headers=None, timeout=None):
        captured["url"] = url
        request = httpx.Request("GET", url)
        return httpx.Response(200, json={"code": "00000", "data": []}, request=request)

    monkeypatch.setattr(httpx, "get", _mock_get)

    BitgetProvider().get_tax_spot_records(1000, 2000, limit=50)

    # alphabetical: endTime, limit, startTime -- must match how the signature was built.
    assert captured["url"] == "https://api.bitget.com/api/v2/tax/spot-record?endTime=2000&limit=50&startTime=1000"

    get_settings.cache_clear()


def test_network_error_is_error_status_not_exception(monkeypatch):
    monkeypatch.setenv("BITGET_API_KEY", "key123")
    monkeypatch.setenv("BITGET_API_SECRET", "secret456")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "phrase789")
    get_settings.cache_clear()

    def _raising_get(url, headers=None, timeout=None):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "get", _raising_get)

    result = BitgetProvider().get_balance()

    assert result.status == "error"
    assert "connection refused" in result.error_message

    get_settings.cache_clear()
