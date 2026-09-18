"""Logging configuration and per-request correlation.

``configure_logging()`` builds the stdlib ``dictConfig`` once, from the FastAPI
lifespan: uvicorn installs its own config at startup, so configuring at import
time would be overwritten. A request id travels in a ContextVar and is injected
into every record by ``RequestIdFilter``, so one id greps a whole upload's
lifecycle.
"""

import logging
import logging.config
import uuid
from contextvars import ContextVar
from typing import Any

from app.config import get_settings

_REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="-")

_LOG_FORMAT = "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"


def set_request_id(value: str | None = None) -> str:
    """Set the request id for the current context and return it."""
    request_id = value or uuid.uuid4().hex[:12]
    _REQUEST_ID.set(request_id)
    return request_id


def get_request_id() -> str:
    """Return the request id for the current context."""
    return _REQUEST_ID.get()


def reset_request_id() -> None:
    """Clear the request id for the current context."""
    _REQUEST_ID.set("-")


class RequestIdFilter(logging.Filter):
    """Attach the current request id to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


def configure_logging() -> None:
    """Configure the stdlib logging stack; run once from the lifespan."""
    level = get_settings().log_level
    sqlalchemy_level = "INFO" if level == "DEBUG" else "WARNING"

    config: dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {"request_id": {"()": RequestIdFilter}},
        "formatters": {"default": {"format": _LOG_FORMAT}},
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "filters": ["request_id"],
            }
        },
        "root": {"handlers": ["console"], "level": level},
        "loggers": {
            "uvicorn": {"level": level, "handlers": ["console"], "propagate": False},
            "uvicorn.error": {
                "level": level,
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False,
            },
            "sqlalchemy.engine": {
                "level": sqlalchemy_level,
                "handlers": ["console"],
                "propagate": False,
            },
        },
    }
    logging.config.dictConfig(config)
