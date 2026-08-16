from decimal import Decimal

from fastapi.testclient import TestClient

from app.core.config import get_settings


def test_create_entry_with_quantity_via_api(authed_client: TestClient, today, monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE", "mock")
    get_settings.cache_clear()

    response = authed_client.post(
        "/api/financials/entries",
        json={
            "entry_type": "asset",
            "category": "holding",
            "subcategory": "btc",
            "label": "Bitvavo Wallet",
            "quantity": "0.2",
            "price_asset_id": "bitcoin",
            "currency": "EUR",
            "snapshot_date": today.isoformat(),
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert Decimal(body["amount"]) == Decimal("12000.00")
    assert Decimal(body["quantity"]) == Decimal("0.2")

    get_settings.cache_clear()


def test_create_entry_unknown_coin_returns_400(authed_client: TestClient, today, monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE", "mock")
    get_settings.cache_clear()

    response = authed_client.post(
        "/api/financials/entries",
        json={
            "entry_type": "asset",
            "category": "holding",
            "subcategory": "crypto",
            "label": "Mystery Coin",
            "quantity": "10",
            "price_asset_id": "not-a-real-coin",
            "snapshot_date": today.isoformat(),
        },
    )

    assert response.status_code == 400

    get_settings.cache_clear()


def test_refresh_value_endpoint(authed_client: TestClient, today, monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE", "mock")
    get_settings.cache_clear()

    create_response = authed_client.post(
        "/api/financials/entries",
        json={
            "entry_type": "asset",
            "category": "holding",
            "subcategory": "btc",
            "label": "Bitvavo Wallet",
            "quantity": "0.5",
            "price_asset_id": "bitcoin",
            "snapshot_date": today.isoformat(),
        },
    )
    entry_id = create_response.json()["id"]

    refresh_response = authed_client.post(f"/api/financials/entries/{entry_id}/refresh-value")

    assert refresh_response.status_code == 200
    assert Decimal(refresh_response.json()["amount"]) == Decimal("30000.00")

    get_settings.cache_clear()


def test_refresh_value_without_quantity_returns_400(authed_client: TestClient, today, monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE", "mock")
    get_settings.cache_clear()

    create_response = authed_client.post(
        "/api/financials/entries",
        json={
            "entry_type": "asset",
            "category": "holding",
            "subcategory": "cash",
            "label": "checking",
            "amount": "500.00",
            "snapshot_date": today.isoformat(),
        },
    )
    entry_id = create_response.json()["id"]

    response = authed_client.post(f"/api/financials/entries/{entry_id}/refresh-value")

    assert response.status_code == 400

    get_settings.cache_clear()


def test_refresh_value_not_found_returns_404(authed_client: TestClient):
    response = authed_client.post("/api/financials/entries/999999/refresh-value")
    assert response.status_code == 404
