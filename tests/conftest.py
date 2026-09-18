"""Shared pytest fixtures.

Repository and API tests run against a dedicated throwaway database
(`anomaly_test`, created by docker/initdb). They never touch the dev database.
Each test starts from truncated tables via the `session` / `client` fixtures.
"""

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.data.tables import Base

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://anomaly:anomaly@localhost:5432/anomaly_test",
)

_TABLES = ("uploads", "events", "anomalies", "narratives")


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    test_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    test_engine.dispose()


def _truncate(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(f"TRUNCATE {', '.join(_TABLES)} RESTART IDENTITY CASCADE")
        )


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    _truncate(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    from app.data.session import get_session
    from app.main import app

    _truncate(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_session() -> Iterator[Session]:
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_session] = override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
