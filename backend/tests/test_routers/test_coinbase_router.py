from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.providers.coinbase_provider import CoinbaseProvider, CoinbaseResult
from app.services import coinbase_sync_service


def test_status_requires_auth(client: TestClient):
    response = client.get("/api/integrations/coinbase/status")
    assert response.status_code == 401


def test_status_reports_not_configured_without_keys(authed_client: TestClient, monkeypatch):
    monkeypatch.setenv("COINBASE_API_KEY_NAME", "")
    monkeypatch.setenv("COINBASE_API_PRIVATE_KEY", "")
    get_settings.cache_clear()

    response = authed_client.get("/api/integrations/coinbase/status")

    assert response.status_code == 200
    assert response.json() == {"configured": False}

    get_settings.cache_clear()


def test_status_reports_configured_with_both_values(authed_client: TestClient, monkeypatch):
    monkeypatch.setenv("COINBASE_API_KEY_NAME", "organizations/org/apiKeys/key")
    monkeypatch.setenv("COINBASE_API_PRIVATE_KEY", "some-pem-block")
    get_settings.cache_clear()

    response = authed_client.get("/api/integrations/coinbase/status")

    assert response.json() == {"configured": True}

    get_settings.cache_clear()


def test_sync_requires_auth(client: TestClient):
    response = client.post("/api/integrations/coinbase/sync")
    assert response.status_code == 401


def test_sync_without_keys_reports_not_configured(authed_client: TestClient, monkeypatch):
    monkeypatch.setenv("COINBASE_API_KEY_NAME", "")
    monkeypatch.setenv("COINBASE_API_PRIVATE_KEY", "")
    get_settings.cache_clear()

    response = authed_client.post("/api/integrations/coinbase/sync")

    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is False
    assert body["assets"] == []

    get_settings.cache_clear()


def test_sync_with_mocked_provider_returns_assets(authed_client: TestClient, monkeypatch):
    monkeypatch.setenv("COINBASE_API_KEY_NAME", "organizations/org/apiKeys/key")
    monkeypatch.setenv("COINBASE_API_PRIVATE_KEY", "some-pem-block")
    monkeypatch.setenv("MARKET_DATA_MODE", "mock")
    get_settings.cache_clear()
    monkeypatch.setattr(coinbase_sync_service.time, "sleep", lambda *_: None)

    monkeypatch.setattr(CoinbaseProvider, "is_configured", property(lambda self: True))
    monkeypatch.setattr(
        CoinbaseProvider,
        "get_accounts",
        lambda self, cursor=None: CoinbaseResult(
            "ok", {"accounts": [{"currency": "BTC", "available_balance": {"value": "0.1"}, "hold": {"value": "0"}}], "has_next": False}
        ),
    )
    monkeypatch.setattr(
        CoinbaseProvider,
        "get_fills",
        lambda self, cursor=None, product_ids=None: CoinbaseResult(
            "ok",
            {
                "fills": [
                    {
                        "product_id": "BTC-EUR",
                        "price": "50000",
                        "size": "0.1",
                        "side": "BUY",
                        "trade_id": "t1",
                        "trade_time": "2024-07-05T12:00:00Z",
                    }
                ],
                "has_next": False,
            },
        ),
    )

    response = authed_client.post("/api/integrations/coinbase/sync")

    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is True
    assert len(body["assets"]) == 1
    assert body["assets"][0]["symbol"] == "BTC"
    assert body["assets"][0]["quantity"] == "0.1000000000"

    get_settings.cache_clear()
