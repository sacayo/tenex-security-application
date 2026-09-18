"""Application settings loaded from environment variables.

Single source of deploy-time configuration so no module hardcodes
environment-specific values. ``python-dotenv`` loads ``.env`` locally; a
hosted platform injects real variables. See ``.env.example``.
"""

import os
from dataclasses import dataclass, field
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

_DEFAULT_DATABASE_URL = "postgresql+psycopg://anomaly:anomaly@localhost:5432/anomaly"
_DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://localhost:8000"
_DEFAULT_LLM_MODEL = "nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16"


def _csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _number(name: str, default: float) -> float:
    value = os.environ.get(name)
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Runtime configuration resolved from environment variables."""

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

    # --- LLM narrative layer (spec.md - "LLM narrative layer") ---------------
    # Off by default: the API is fully functional without a model endpoint;
    # the narrative card simply does not render.
    llm_enabled: bool = field(default_factory=lambda: _flag("LLM_ENABLED"))
    # OpenAI-compatible base URL, e.g. https://<ws>--<app>-serve.modal.run/v1
    llm_base_url: str = field(
        default_factory=lambda: os.environ.get("LLM_BASE_URL", "").rstrip("/")
    )
    # Sent as `Authorization: Bearer ...`. With Modal proxy auth this is the
    # Modal token; the vLLM server behind it must NOT also set --api-key.
    llm_api_key: str = field(default_factory=lambda: os.environ.get("LLM_API_KEY", ""))
    # Must equal the server's --served-model-name.
    llm_model: str = field(
        default_factory=lambda: os.environ.get("LLM_MODEL", _DEFAULT_LLM_MODEL)
    )
    # Generous on purpose: a scale-to-zero Modal container boots inside this
    # window and looks like a slow response, not a connection error.
    llm_timeout_seconds: float = field(
        default_factory=lambda: _number("LLM_TIMEOUT_SECONDS", 300)
    )
    # Minimum gap between forced regenerations (?refresh=true) per upload.
    llm_refresh_cooldown_seconds: float = field(
        default_factory=lambda: _number("LLM_REFRESH_COOLDOWN_SECONDS", 300)
    )

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance."""
    return Settings()
