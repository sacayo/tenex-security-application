"""Engine + session factory.

The only place that knows how to connect to the database. The connection
string comes from `DATABASE_URL` so the same code runs on a laptop (localhost),
inside Docker Compose (hostname `db`), and on a PaaS whose injected URL may
omit the driver. Layering rules: spec.md - "Architecture Overview".
"""

import logging
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

logger = logging.getLogger(__name__)


def normalize_database_url(url: str) -> str:
    """Force the psycopg (v3) driver.

    PaaS providers and Supabase hand out `postgres://` or `postgresql://`
    URLs, which SQLAlchemy maps to the psycopg2 dialect. Rewriting to
    `postgresql+psycopg://` selects the driver we actually install.
    """
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


settings = get_settings()
DATABASE_URL = normalize_database_url(settings.database_url)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
)

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


def factory_for(session: Session) -> sessionmaker[Session]:
    """A session factory bound to the same engine as `session`.

    Background tasks outlive the request session that scheduled them and
    must open their own. Deriving the factory from the live session (rather
    than using the module-level `SessionLocal`) keeps the test suite's
    `get_session` override pointing at the throwaway database.
    """
    return sessionmaker(
        bind=session.get_bind(), autoflush=False, expire_on_commit=False
    )
