"""Engine + session factory.

The only place that knows how to connect to the database. The connection
string comes from `DATABASE_URL` so the same code runs on a laptop (localhost)
and inside Docker Compose (hostname `db`). Layering rules: spec.md - "Architecture Overview".
"""

import logging
import os
from collections.abc import Iterator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://anomaly:anomaly@localhost:5432/anomaly",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def log_engine_target() -> None:
    """Log where the engine points WITHOUT exposing the password."""
    url = make_url(DATABASE_URL)
    logger.debug(
        "engine target driver=%s host=%s port=%s db=%s",
        url.drivername,
        url.host,
        url.port,
        url.database,
    )


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yield a session and always close it."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
