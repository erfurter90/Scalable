from fastapi.testclient import TestClient

from app.core.config import get_settings


def test_status_requires_auth(client: TestClient):
    response = client.get("/api/chat/status")
    assert response.status_code == 401


def test_status_reports_not_configured_without_key(authed_client: TestClient, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    get_settings.cache_clear()

    response = authed_client.get("/api/chat/status")

    assert response.status_code == 200
    assert response.json() == {"configured": False}

    get_settings.cache_clear()


def test_message_without_key_returns_ai_unavailable(authed_client: TestClient, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    get_settings.cache_clear()

    response = authed_client.post("/api/chat/message", json={"message": "Wie viel Cash habe ich?"})

    assert response.status_code == 200
    body = response.json()
    assert body["ai_available"] is False
    assert body["reply"] is None

    get_settings.cache_clear()
