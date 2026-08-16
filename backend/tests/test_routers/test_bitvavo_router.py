from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.providers.bitvavo_provider import BitvavoProvider, BitvavoResult


def test_status_requires_auth(client: TestClient):
    response = client.get("/api/integrations/bitvavo/status")
    assert response.status_code == 401


def test_status_reports_not_configured_without_keys(authed_client: TestClient, monkeypatch):
    monkeypatch.setenv("BITVAVO_API_KEY", "")
    monkeypatch.setenv("BITVAVO_API_SECRET", "")
    get_settings.cache_clear()

    response = authed_client.get("/api/integrations/bitvavo/status")

    assert response.status_code == 200
    assert response.json() == {"configured": False}

    get_settings.cache_clear()


def test_status_reports_configured_with_keys(authed_client: TestClient, monkeypatch):
    monkeypatch.setenv("BITVAVO_API_KEY", "key")
    monkeypatch.setenv("BITVAVO_API_SECRET", "secret")
    get_settings.cache_clear()

    response = authed_client.get("/api/integrations/bitvavo/status")

    assert response.json() == {"configured": True}

    get_settings.cache_clear()


def test_sync_requires_auth(client: TestClient):
    response = client.post("/api/integrations/bitvavo/sync")
    assert response.status_code == 401


def test_sync_without_keys_reports_not_configured(authed_client: TestClient, monkeypatch):
    monkeypatch.setenv("BITVAVO_API_KEY", "")
    monkeypatch.setenv("BITVAVO_API_SECRET", "")
    get_settings.cache_clear()

    response = authed_client.post("/api/integrations/bitvavo/sync")

    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is False
    assert body["assets"] == []

    get_settings.cache_clear()


def test_sync_with_mocked_provider_returns_assets(authed_client: TestClient, monkeypatch):
    monkeypatch.setenv("BITVAVO_API_KEY", "key")
    monkeypatch.setenv("BITVAVO_API_SECRET", "secret")
    monkeypatch.setenv("MARKET_DATA_MODE", "mock")
    get_settings.cache_clear()

    monkeypatch.setattr(BitvavoProvider, "is_configured", property(lambda self: True))
    monkeypatch.setattr(
        BitvavoProvider,
        "get_balance",
        lambda self, symbol=None: BitvavoResult("ok", [{"symbol": "BTC", "available": "0.1", "inOrder": "0"}]),
    )
    monkeypatch.setattr(
        BitvavoProvider,
        "get_trades",
        lambda self, market, limit=1000, trade_id_from=None: BitvavoResult(
            "ok",
            [{"id": "trade-1", "timestamp": 1700000000000, "amount": "0.1", "price": "50000", "side": "buy", "fee": "0"}],
        ),
    )
    monkeypatch.setattr(
        BitvavoProvider, "get_deposit_history", lambda self, symbol=None, limit=1000: BitvavoResult("ok", [])
    )
    monkeypatch.setattr(
        BitvavoProvider, "get_withdrawal_history", lambda self, symbol=None, limit=1000: BitvavoResult("ok", [])
    )

    response = authed_client.post("/api/integrations/bitvavo/sync")

    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is True
    assert len(body["assets"]) == 1
    assert body["assets"][0]["symbol"] == "BTC"
    assert body["assets"][0]["quantity"] == "0.1000000000"
    assert body["assets"][0]["average_cost_basis"] == "50000.00"

    get_settings.cache_clear()
