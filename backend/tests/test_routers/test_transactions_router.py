from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.models.transaction import Transaction, TransactionType


def test_recent_requires_auth(client: TestClient):
    response = client.get("/api/transactions/recent")
    assert response.status_code == 401


def test_recent_returns_transactions(authed_client: TestClient, db_session, test_user):
    db_session.add(
        Transaction(
            user_id=test_user.id,
            date=datetime(2026, 8, 16, tzinfo=UTC).date(),
            occurred_at=datetime(2026, 8, 16, 12, 30, tzinfo=UTC),
            type=TransactionType.buy,
            asset="BTC",
            amount="0.1",
            price="50000",
            fee=None,
            currency="EUR",
            source="bitget",
            external_id="t1",
        )
    )
    db_session.commit()

    response = authed_client.get("/api/transactions/recent")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["source"] == "Bitget"
    assert body[0]["asset"] == "BTC"
    assert body[0]["price"] == "50000.00000000"
    assert body[0]["total_cost"] == "5000.000000000000000000"
    assert body[0]["occurred_at"] == "2026-08-16T12:30:00"


def test_recent_returns_empty_list_without_transactions(authed_client: TestClient):
    response = authed_client.get("/api/transactions/recent")

    assert response.status_code == 200
    assert response.json() == []
