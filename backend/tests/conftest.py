"""
Shared pytest fixtures.

The API tests run against SQLite in memory by default, so `pytest` works on a
laptop with no services running. The models use SQLAlchemy's dialect-agnostic
`Uuid` type (they previously used the postgresql-only `UUID`, which made this
impossible), so the same schema builds on both engines.

Set TEST_DATABASE_URL to run the identical suite against real Postgres. CI does
this, because SQLite is more permissive than Postgres and quietly accepts things
Postgres rejects — a GROUP BY on a `coalesce()` expression passed every SQLite
test and then 500'd on the first real query against Postgres.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Must be set before app.core.config is imported anywhere.
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-value-that-is-long-enough-for-hs256-ok")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.api.auth import auth_limiter  # noqa: E402
from app.db.base import Base, import_all_models  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402

import_all_models()


TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite://")


@pytest.fixture
def db_session():
    if TEST_DATABASE_URL.startswith("sqlite"):
        engine = create_engine(
            TEST_DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,   # one shared in-memory DB across connections
        )
    else:
        engine = create_engine(TEST_DATABASE_URL, poolclass=StaticPool)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    auth_limiter.reset()   # otherwise limits leak between tests
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_client(client):
    """A registered, logged-in client with the bearer token already attached."""
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "student@example.com",
            "password": "correct-horse-battery",
            "full_name": "Test Student",
        },
    )
    assert res.status_code == 201, res.text
    client.headers["Authorization"] = f"Bearer {res.json()['access_token']}"
    return client
