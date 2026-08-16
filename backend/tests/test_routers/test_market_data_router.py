from fastapi.testclient import TestClient

from app.core.config import get_settings


def test_snapshot_requires_auth(client: TestClient):
    response = client.get("/api/market/snapshot")
    assert response.status_code == 401


def test_btc_price_uses_mock_provider(authed_client: TestClient, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("MARKET_DATA_MODE", "mock")
    get_settings.cache_clear()

    response = authed_client.get("/api/market/btc-price")

    assert response.status_code == 200
    body = response.json()
    assert body["usd"]["status"] == "ok"
    assert body["usd"]["source"] == "mock"
    assert body["usd"]["value"] == 65000.0

    get_settings.cache_clear()


def test_fear_greed_uses_mock_provider(authed_client: TestClient, monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE", "mock")
    get_settings.cache_clear()

    response = authed_client.get("/api/market/fear-greed")

    assert response.status_code == 200
    body = response.json()
    assert body["index"]["status"] == "ok"
    assert body["index"]["source"] == "mock"

    get_settings.cache_clear()
