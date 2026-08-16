from decimal import Decimal

from fastapi.testclient import TestClient

from app.core.config import get_settings


def test_create_entry_with_purchase_price_via_api(authed_client: TestClient, today, monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE", "mock")
    get_settings.cache_clear()

    response = authed_client.post(
        "/api/financials/entries",
        json={
            "entry_type": "asset",
            "category": "holding",
            "subcategory": "btc",
            "label": "wallet",
            "quantity": "0.1",
            "price_asset_id": "bitcoin",
            "purchase_price": "50000",
            "purchase_price_currency": "USD",
            "snapshot_date": today.isoformat(),
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert Decimal(body["average_cost_basis"]) == Decimal("46000.00")

    get_settings.cache_clear()


def test_add_purchase_endpoint_blends_average(authed_client: TestClient, today, monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE", "mock")
    get_settings.cache_clear()

    create_response = authed_client.post(
        "/api/financials/entries",
        json={
            "entry_type": "asset",
            "category": "holding",
            "subcategory": "btc",
            "label": "wallet",
            "quantity": "0.1",
            "price_asset_id": "bitcoin",
            "purchase_price": "50000",
            "purchase_price_currency": "EUR",
            "snapshot_date": today.isoformat(),
        },
    )
    entry_id = create_response.json()["id"]

    response = authed_client.post(
        f"/api/financials/entries/{entry_id}/add-purchase",
        json={"additional_quantity": "0.1", "purchase_price": "60000", "purchase_price_currency": "EUR"},
    )

    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["average_cost_basis"]) == Decimal("55000.00")
    assert Decimal(body["quantity"]) == Decimal("0.2")

    get_settings.cache_clear()


def test_add_purchase_without_quantity_returns_400(authed_client: TestClient, today):
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

    response = authed_client.post(
        f"/api/financials/entries/{entry_id}/add-purchase",
        json={"additional_quantity": "1", "purchase_price": "100", "purchase_price_currency": "EUR"},
    )

    assert response.status_code == 400


def test_add_purchase_not_found_returns_404(authed_client: TestClient):
    response = authed_client.post(
        "/api/financials/entries/999999/add-purchase",
        json={"additional_quantity": "1", "purchase_price": "100", "purchase_price_currency": "EUR"},
    )
    assert response.status_code == 404


def test_add_purchase_requires_auth(client: TestClient):
    response = client.post(
        "/api/financials/entries/1/add-purchase",
        json={"additional_quantity": "1", "purchase_price": "100", "purchase_price_currency": "EUR"},
    )
    assert response.status_code == 401


def test_add_purchase_without_existing_cost_basis_returns_400(authed_client: TestClient, today, monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE", "mock")
    get_settings.cache_clear()

    create_response = authed_client.post(
        "/api/financials/entries",
        json={
            "entry_type": "asset",
            "category": "holding",
            "subcategory": "btc",
            "label": "wallet",
            "quantity": "0.1",
            "price_asset_id": "bitcoin",
            "snapshot_date": today.isoformat(),
        },
    )
    entry_id = create_response.json()["id"]

    response = authed_client.post(
        f"/api/financials/entries/{entry_id}/add-purchase",
        json={"additional_quantity": "0.1", "purchase_price": "60000", "purchase_price_currency": "EUR"},
    )

    assert response.status_code == 400

    get_settings.cache_clear()


def test_set_cost_basis_endpoint(authed_client: TestClient, today, monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE", "mock")
    get_settings.cache_clear()

    create_response = authed_client.post(
        "/api/financials/entries",
        json={
            "entry_type": "asset",
            "category": "holding",
            "subcategory": "crypto",
            "label": "ETH wallet",
            "quantity": "182.570665",
            "price_asset_id": "ethereum",
            "snapshot_date": today.isoformat(),
        },
    )
    entry_id = create_response.json()["id"]
    assert create_response.json()["average_cost_basis"] is None

    response = authed_client.post(
        f"/api/financials/entries/{entry_id}/set-cost-basis",
        json={"purchase_price": "0.55", "purchase_price_currency": "EUR"},
    )

    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["average_cost_basis"]) == Decimal("0.55")
    assert Decimal(body["quantity"]) == Decimal("182.570665")

    get_settings.cache_clear()


def test_set_cost_basis_without_quantity_returns_400(authed_client: TestClient, today):
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

    response = authed_client.post(
        f"/api/financials/entries/{entry_id}/set-cost-basis",
        json={"purchase_price": "100", "purchase_price_currency": "EUR"},
    )

    assert response.status_code == 400


def test_set_cost_basis_not_found_returns_404(authed_client: TestClient):
    response = authed_client.post(
        "/api/financials/entries/999999/set-cost-basis",
        json={"purchase_price": "100", "purchase_price_currency": "EUR"},
    )
    assert response.status_code == 404


def test_set_cost_basis_requires_auth(client: TestClient):
    response = client.post(
        "/api/financials/entries/1/set-cost-basis",
        json={"purchase_price": "100", "purchase_price_currency": "EUR"},
    )
    assert response.status_code == 401
