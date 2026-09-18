"""Application settings, read from environment variables.

One place for deploy-time configuration so no module hardcodes
environment-specific values. Locally, `python-dotenv` loads `.env`; on
Railway/Vercel the platform injects real environment variables.
"""

import os
from dataclasses import dataclass, field
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

_DEFAULT_DATABASE_URL = "postgresql+psycopg://anomaly:anomaly@localhost:5432/anomaly"
_DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://localhost:8000"


def _csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: os.environ.get("DATABASE_URL", _DEFAULT_DATABASE_URL)
    )
    cors_origins: list[str] = field(
        default_factory=lambda: _csv(
            os.environ.get("CORS_ORIGINS", _DEFAULT_CORS_ORIGINS)
        )
    )
    cors_origin_regex: str | None = field(
        default_factory=lambda: os.environ.get("CORS_ORIGIN_REGEX") or None
    )
    log_level: str = field(
        default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO").upper()
    )
    environment: str = field(
        default_factory=lambda: os.environ.get("ENVIRONMENT", "development")
    )

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
