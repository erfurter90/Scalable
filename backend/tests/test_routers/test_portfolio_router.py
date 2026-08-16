from fastapi.testclient import TestClient


def test_allocation_requires_auth(client: TestClient):
    response = client.get("/api/portfolio/allocation")
    assert response.status_code == 401


def test_allocation_404_without_data(authed_client: TestClient):
    response = authed_client.get("/api/portfolio/allocation")
    assert response.status_code == 404


def test_allocation_after_entries(authed_client: TestClient, today):
    authed_client.post(
        "/api/financials/entries",
        json={
            "entry_type": "asset",
            "category": "holding",
            "subcategory": "btc",
            "label": "wallet",
            "amount": "1000.00",
            "snapshot_date": today.isoformat(),
        },
    )

    response = authed_client.get("/api/portfolio/allocation")

    assert response.status_code == 200
    body = response.json()
    assert body["btc_percent_of_assets"] == 100.0


def test_crypto_breakdown_requires_auth(client: TestClient):
    response = client.get("/api/portfolio/crypto-breakdown")
    assert response.status_code == 401


def test_crypto_breakdown_404_without_crypto_data(authed_client: TestClient):
    response = authed_client.get("/api/portfolio/crypto-breakdown")
    assert response.status_code == 404


def test_crypto_breakdown_after_entries(authed_client: TestClient, today):
    authed_client.post(
        "/api/financials/entries",
        json={
            "entry_type": "asset",
            "category": "holding",
            "subcategory": "crypto",
            "label": "SOL wallet",
            "amount": "300.00",
            "price_asset_id": "solana",
            "snapshot_date": today.isoformat(),
        },
    )
    authed_client.post(
        "/api/financials/entries",
        json={
            "entry_type": "asset",
            "category": "holding",
            "subcategory": "crypto",
            "label": "ETH wallet",
            "amount": "700.00",
            "price_asset_id": "ethereum",
            "snapshot_date": today.isoformat(),
        },
    )

    response = authed_client.get("/api/portfolio/crypto-breakdown")

    assert response.status_code == 200
    body = response.json()
    assert body["total_crypto"] == "1000.00"
    by_coin = {item["coin"]: item["percent_of_crypto"] for item in body["breakdown"]}
    assert by_coin["solana"] == 30.0
    assert by_coin["ethereum"] == 70.0
