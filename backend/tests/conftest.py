"""Shared pytest fixtures: in-memory SQLite DB, a TestClient wired to it, and a logged-in
client. No test in this suite hits a live network endpoint — providers are monkeypatched
or exercised via MockProvider instead."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import ScoringWeightsConfig, User


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = TestingSessionLocal()
    session.add(
        ScoringWeightsConfig(
            version=1,
            valuation_weight=0.25,
            sentiment_weight=0.20,
            cycle_weight=0.20,
            macro_weight=0.15,
            momentum_weight=0.10,
            onchain_weight=0.10,
            is_active=True,
        )
    )
    session.commit()

    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session: Session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    app.state.limiter.reset()  # rate-limit counters persist across tests otherwise (shared in-memory storage)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def test_user(db_session: Session) -> User:
    user = User(username="testuser", hashed_password=hash_password("testpass123"))
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def authed_client(client: TestClient, test_user: User) -> TestClient:
    response = client.post("/api/auth/login", json={"username": "testuser", "password": "testpass123"})
    assert response.status_code == 200
    return client


@pytest.fixture()
def today() -> date:
    return date(2026, 8, 16)
