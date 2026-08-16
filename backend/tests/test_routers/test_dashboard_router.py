from fastapi.testclient import TestClient

from app.core.config import get_settings


def test_dashboard_requires_auth(client: TestClient):
    response = client.get("/api/dashboard")
    assert response.status_code == 401


def test_dashboard_without_financial_data(authed_client: TestClient, monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE", "mock")
    get_settings.cache_clear()

    response = authed_client.get("/api/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["net_worth"] is None
    assert body["portfolio"] is None
    assert body["crypto_breakdown"] is None
    assert body["market"]["btc"]["usd"]["status"] == "ok"
    assert body["score"]["total_score"] is not None

    get_settings.cache_clear()


def test_dashboard_with_financial_data(authed_client: TestClient, monkeypatch, today):
    monkeypatch.setenv("MARKET_DATA_MODE", "mock")
    get_settings.cache_clear()

    authed_client.post(
        "/api/financials/entries",
        json={
            "entry_type": "asset",
            "category": "holding",
            "subcategory": "cash",
            "label": "checking",
            "amount": "1000.00",
            "currency": "EUR",
            "snapshot_date": today.isoformat(),
        },
    )
    authed_client.post(
        "/api/financials/entries",
        json={
            "entry_type": "asset",
            "category": "holding",
            "subcategory": "crypto",
            "label": "SOL wallet",
            "amount": "500.00",
            "price_asset_id": "solana",
            "snapshot_date": today.isoformat(),
        },
    )

    response = authed_client.get("/api/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["net_worth"]["net_worth"] == "1500.00"
    assert body["portfolio"]["total_assets"] == "1500.00"
    assert body["crypto_breakdown"]["total_crypto"] == "500.00"
    assert body["crypto_breakdown"]["breakdown"][0]["coin"] == "solana"

    get_settings.cache_clear()
