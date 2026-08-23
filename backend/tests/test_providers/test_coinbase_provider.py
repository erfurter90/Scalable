import jwt
import httpx
from cryptography.hazmat.primitives import serialization

from app.core.config import get_settings
from app.providers.coinbase_provider import CoinbaseProvider, sign_for_test

# Test-only EC P-256 key pair, generated once for this suite -- not a real credential.
_TEST_PRIVATE_KEY_PEM = """-----BEGIN PRIVATE KEY-----
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgE8/fRIZ/+QX6EdID
ZdKoFi/ab2iC21ySMc0wazUqRWGhRANCAAQMjoHNU08wISC9usx2zceQil+TQOHv
2IsG5Z0AXM0ku6kdIAuN/E++fHazJqfpQeF/GBqN80oNMTUKcH5rEKVf
-----END PRIVATE KEY-----"""

_TEST_KEY_NAME = "organizations/test-org/apiKeys/test-key"


def _test_public_key():
    private_key = serialization.load_pem_private_key(_TEST_PRIVATE_KEY_PEM.encode(), password=None)
    return private_key.public_key()


def test_jwt_is_valid_and_decodes_with_matching_public_key():
    # Coinbase publishes no fixed test vector (unlike Bitvavo) -- verified instead by building
    # a JWT with a locally generated key pair and confirming it decodes correctly with the
    # matching public key, using the exact algorithm/claims documented in the official SDK.
    token = sign_for_test(
        "GET", "/api/v3/brokerage/accounts", _TEST_KEY_NAME, _TEST_PRIVATE_KEY_PEM
    )

    decoded = jwt.decode(token, _test_public_key(), algorithms=["ES256"])

    assert decoded["sub"] == _TEST_KEY_NAME
    assert decoded["iss"] == "cdp"
    assert decoded["uri"] == "GET api.coinbase.com/api/v3/brokerage/accounts"
    assert decoded["exp"] - decoded["nbf"] == 120

    header = jwt.get_unverified_header(token)
    assert header["kid"] == _TEST_KEY_NAME
    assert header["alg"] == "ES256"
    assert "nonce" in header


def test_jwt_handles_escaped_newlines_from_env_file():
    # .env values can't contain real newlines -- the PEM is stored with literal "\n" and must
    # be unescaped before use.
    escaped_pem = _TEST_PRIVATE_KEY_PEM.replace("\n", "\\n")

    token = sign_for_test("GET", "/api/v3/brokerage/accounts", _TEST_KEY_NAME, escaped_pem)

    decoded = jwt.decode(token, _test_public_key(), algorithms=["ES256"])
    assert decoded["sub"] == _TEST_KEY_NAME


def test_is_configured_requires_both_values(monkeypatch):
    monkeypatch.setenv("COINBASE_API_KEY_NAME", _TEST_KEY_NAME)
    monkeypatch.setenv("COINBASE_API_PRIVATE_KEY", "")
    get_settings.cache_clear()

    assert CoinbaseProvider().is_configured is False

    monkeypatch.setenv("COINBASE_API_PRIVATE_KEY", _TEST_PRIVATE_KEY_PEM.replace("\n", "\\n"))
    get_settings.cache_clear()

    assert CoinbaseProvider().is_configured is True

    get_settings.cache_clear()


def test_get_accounts_not_configured_returns_error(monkeypatch):
    monkeypatch.setenv("COINBASE_API_KEY_NAME", "")
    monkeypatch.setenv("COINBASE_API_PRIVATE_KEY", "")
    get_settings.cache_clear()

    result = CoinbaseProvider().get_accounts()

    assert result.status == "error"
    assert result.data is None

    get_settings.cache_clear()


def test_get_accounts_ok_sends_bearer_token(monkeypatch):
    monkeypatch.setenv("COINBASE_API_KEY_NAME", _TEST_KEY_NAME)
    monkeypatch.setenv("COINBASE_API_PRIVATE_KEY", _TEST_PRIVATE_KEY_PEM.replace("\n", "\\n"))
    get_settings.cache_clear()

    captured = {}

    def _mock_get(url, headers=None, params=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["params"] = params
        request = httpx.Request("GET", url)
        return httpx.Response(200, json={"accounts": [{"currency": "BTC", "available_balance": {"value": "0.5"}}]}, request=request)

    monkeypatch.setattr(httpx, "get", _mock_get)

    result = CoinbaseProvider().get_accounts()

    assert result.status == "ok"
    assert result.data == {"accounts": [{"currency": "BTC", "available_balance": {"value": "0.5"}}]}
    assert captured["url"] == "https://api.coinbase.com/api/v3/brokerage/accounts"
    assert captured["headers"]["Authorization"].startswith("Bearer ")

    token = captured["headers"]["Authorization"].removeprefix("Bearer ")
    decoded = jwt.decode(token, _test_public_key(), algorithms=["ES256"])
    assert decoded["uri"] == "GET api.coinbase.com/api/v3/brokerage/accounts"

    get_settings.cache_clear()


def test_get_fills_passes_cursor_and_product_ids(monkeypatch):
    monkeypatch.setenv("COINBASE_API_KEY_NAME", _TEST_KEY_NAME)
    monkeypatch.setenv("COINBASE_API_PRIVATE_KEY", _TEST_PRIVATE_KEY_PEM.replace("\n", "\\n"))
    get_settings.cache_clear()

    captured = {}

    def _mock_get(url, headers=None, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        request = httpx.Request("GET", url)
        return httpx.Response(200, json={"fills": [], "has_next": False}, request=request)

    monkeypatch.setattr(httpx, "get", _mock_get)

    CoinbaseProvider().get_fills(cursor="abc123", product_ids=["ETH-EUR"])

    assert captured["url"] == "https://api.coinbase.com/api/v3/brokerage/orders/historical/fills"
    assert captured["params"] == {"limit": "100", "cursor": "abc123", "product_ids": "ETH-EUR"}

    get_settings.cache_clear()


def test_network_error_is_error_status_not_exception(monkeypatch):
    monkeypatch.setenv("COINBASE_API_KEY_NAME", _TEST_KEY_NAME)
    monkeypatch.setenv("COINBASE_API_PRIVATE_KEY", _TEST_PRIVATE_KEY_PEM.replace("\n", "\\n"))
    get_settings.cache_clear()

    def _raising_get(url, headers=None, params=None, timeout=None):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "get", _raising_get)

    result = CoinbaseProvider().get_accounts()

    assert result.status == "error"
    assert "connection refused" in result.error_message

    get_settings.cache_clear()


def test_invalid_private_key_is_error_status_not_exception(monkeypatch):
    monkeypatch.setenv("COINBASE_API_KEY_NAME", _TEST_KEY_NAME)
    monkeypatch.setenv("COINBASE_API_PRIVATE_KEY", "not-a-valid-pem-block")
    get_settings.cache_clear()

    result = CoinbaseProvider().get_accounts()

    assert result.status == "error"
    assert result.data is None

    get_settings.cache_clear()
