from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.providers.bitget_provider import BitgetProvider, BitgetResult
from app.services import bitget_sync_service


def test_status_requires_auth(client: TestClient):
    response = client.get("/api/integrations/bitget/status")
    assert response.status_code == 401


def test_status_reports_not_configured_without_keys(authed_client: TestClient, monkeypatch):
    monkeypatch.setenv("BITGET_API_KEY", "")
    monkeypatch.setenv("BITGET_API_SECRET", "")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "")
    get_settings.cache_clear()

    response = authed_client.get("/api/integrations/bitget/status")

    assert response.status_code == 200
    assert response.json() == {"configured": False}

    get_settings.cache_clear()


def test_status_reports_configured_with_all_three_keys(authed_client: TestClient, monkeypatch):
    monkeypatch.setenv("BITGET_API_KEY", "key")
    monkeypatch.setenv("BITGET_API_SECRET", "secret")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "phrase")
    get_settings.cache_clear()

    response = authed_client.get("/api/integrations/bitget/status")

    assert response.json() == {"configured": True}

    get_settings.cache_clear()


def test_sync_requires_auth(client: TestClient):
    response = client.post("/api/integrations/bitget/sync")
    assert response.status_code == 401


def test_sync_without_keys_reports_not_configured(authed_client: TestClient, monkeypatch):
    monkeypatch.setenv("BITGET_API_KEY", "")
    monkeypatch.setenv("BITGET_API_SECRET", "")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "")
    get_settings.cache_clear()

    response = authed_client.post("/api/integrations/bitget/sync")

    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is False
    assert body["assets"] == []

    get_settings.cache_clear()


def test_sync_with_mocked_provider_returns_assets(authed_client: TestClient, monkeypatch):
    monkeypatch.setenv("BITGET_API_KEY", "key")
    monkeypatch.setenv("BITGET_API_SECRET", "secret")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "phrase")
    monkeypatch.setenv("MARKET_DATA_MODE", "mock")
    get_settings.cache_clear()
    monkeypatch.setattr(bitget_sync_service.time, "sleep", lambda *_: None)

    monkeypatch.setattr(BitgetProvider, "is_configured", property(lambda self: True))
    monkeypatch.setattr(
        BitgetProvider,
        "get_balance",
        lambda self, coin=None: BitgetResult("ok", [{"coin": "BTC", "available": "0.1", "frozen": "0", "locked": "0"}]),
    )
    records = [
        {"id": "r1", "coin": "BTC", "spotTaxType": "Buy", "amount": "0.1", "fee": "0", "ts": "1700000000000", "bizOrderId": "biz-1"},
        {"id": "r2", "coin": "USDT", "spotTaxType": "Sell", "amount": "-5000", "fee": "0", "ts": "1700000000000", "bizOrderId": "biz-1"},
    ]
    calls = {"n": 0}

    def _get_records(self, start_time_ms, end_time_ms, limit=100):
        calls["n"] += 1
        return BitgetResult("ok", records if calls["n"] == 1 else [])

    monkeypatch.setattr(BitgetProvider, "get_tax_spot_records", _get_records)

    response = authed_client.post("/api/integrations/bitget/sync")

    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is True
    assert len(body["assets"]) == 1
    assert body["assets"][0]["symbol"] == "BTC"
    assert body["assets"][0]["quantity"] == "0.1000000000"

    get_settings.cache_clear()
