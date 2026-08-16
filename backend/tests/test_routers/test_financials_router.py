from decimal import Decimal

from fastapi.testclient import TestClient


def test_entries_require_auth(client: TestClient):
    response = client.get("/api/financials/entries")
    assert response.status_code == 401


def test_create_list_update_delete_entry(authed_client: TestClient, today):
    create_response = authed_client.post(
        "/api/financials/entries",
        json={
            "entry_type": "asset",
            "category": "holding",
            "subcategory": "cash",
            "label": "checking",
            "amount": "500.00",
            "currency": "EUR",
            "snapshot_date": today.isoformat(),
        },
    )
    assert create_response.status_code == 201
    entry_id = create_response.json()["id"]

    list_response = authed_client.get("/api/financials/entries")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    update_response = authed_client.put(f"/api/financials/entries/{entry_id}", json={"amount": "750.00"})
    assert update_response.status_code == 200
    assert Decimal(update_response.json()["amount"]) == Decimal("750.00")

    delete_response = authed_client.delete(f"/api/financials/entries/{entry_id}")
    assert delete_response.status_code == 204

    final_list = authed_client.get("/api/financials/entries")
    assert final_list.json() == []


def test_create_entry_rejects_invalid_subcategory(authed_client: TestClient, today):
    response = authed_client.post(
        "/api/financials/entries",
        json={
            "entry_type": "asset",
            "category": "holding",
            "subcategory": "not_real",
            "label": "x",
            "amount": "100.00",
            "snapshot_date": today.isoformat(),
        },
    )
    assert response.status_code == 400


def test_net_worth_current_404_without_data(authed_client: TestClient):
    response = authed_client.get("/api/financials/net-worth/current")
    assert response.status_code == 404


def test_net_worth_history_after_entries(authed_client: TestClient, today):
    authed_client.post(
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

    response = authed_client.get("/api/financials/net-worth-history")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["net_worth"] == "500.00"
