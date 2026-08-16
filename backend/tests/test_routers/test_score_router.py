import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings


def test_score_requires_auth(client: TestClient):
    response = client.get("/api/score/current")
    assert response.status_code == 401


def test_current_score_with_mock_data(authed_client: TestClient, monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE", "mock")
    get_settings.cache_clear()

    response = authed_client.get("/api/score/current")

    assert response.status_code == 200
    body = response.json()
    assert body["total_score"] is not None
    assert 0 <= body["total_score"] <= 100
    assert body["weights_config_version"] == 1

    by_name = {s["name"]: s for s in body["subscores"]}
    assert by_name["sentiment"]["status"] == "ok"
    assert by_name["momentum"]["status"] == "ok"
    assert by_name["cycle"]["status"] == "ok"
    assert by_name["valuation"]["status"] == "unavailable"
    assert by_name["macro"]["status"] == "unavailable"
    assert by_name["onchain"]["status"] == "unavailable"

    # weight_used for available subscores should sum to ~1.0 (renormalized)
    used_sum = sum(s["weight_used"] for s in body["subscores"] if s["weight_used"] is not None)
    assert used_sum == pytest.approx(1.0, abs=0.01)

    get_settings.cache_clear()


def test_score_history_reflects_persisted_score(authed_client: TestClient, monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE", "mock")
    get_settings.cache_clear()

    authed_client.get("/api/score/current")  # persists today's score
    response = authed_client.get("/api/score/history")

    assert response.status_code == 200
    history = response.json()
    assert len(history) == 1
    assert history[0]["total_score"] is not None

    get_settings.cache_clear()
