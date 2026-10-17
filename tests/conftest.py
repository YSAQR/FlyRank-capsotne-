from __future__ import annotations

import os
import uuid
from collections.abc import Generator

import pytest
from app.core.config import get_settings
from app.db.base import Base
from app.db.seed import run_seed
from app.db.session import get_db
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://flyrank:flyrank_dev_password@localhost:5432/flyrank_billing",
    ),
)
DEV_TOKEN = os.environ.get("TENANT_DEV_TOKEN", "change-me-dev-token")


@pytest.fixture(scope="session")
def engine():
    get_settings.cache_clear()
    eng = create_engine(TEST_DATABASE_URL, pool_pre_ping=True, future=True)
    with eng.connect() as conn:
        conn.execute(text("SELECT 1"))
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine) -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    SessionTesting = sessionmaker(bind=connection, autoflush=False, future=True)
    session = SessionTesting()
    run_seed(session)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(engine) -> Generator[TestClient, None, None]:
    """HTTP client with a committed seed and truncated tables per test."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    seed_session = sessionmaker(bind=engine, future=True)()
    run_seed(seed_session)
    seed_session.close()

    SessionTesting = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def _get_db() -> Generator[Session, None, None]:
        session = SessionTesting()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {
        "X-Dev-Token": DEV_TOKEN,
        "X-Tenant-Id": "11111111-1111-1111-1111-111111111111",
    }


def generate_body(**overrides):
    body = {
        "prompt": "Explain what a reverse proxy does",
        "input_tokens": 120,
        "cached_input_tokens": 20,
        "output_tokens": 80,
        "reasoning_tokens": 15,
    }
    body.update(overrides)
    return body


def new_tenant(client: TestClient, name: str | None = None) -> str:
    response = client.post(
        "/tenants",
        headers={"X-Dev-Token": DEV_TOKEN},
        json={"name": name or f"tenant-{uuid.uuid4().hex[:8]}"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]
