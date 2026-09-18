"""Central logging configuration.

One place to configure the stdlib logging stack for the whole app.
`configure_logging()` is idempotent-ish and meant to run from the FastAPI
lifespan: uvicorn installs its own logging config at startup, so configuring
at import time would be silently overwritten.

A per-request correlation id travels in a ContextVar and is injected into
every log record by `RequestIdFilter`, so a single upload's parse -> detect
-> persist lines can be grepped by one id.
"""

import logging
import logging.config
import os
import uuid
from contextvars import ContextVar
from typing import Any

_REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="-")

_LOG_FORMAT = "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"


def set_request_id(value: str | None = None) -> str:
    request_id = value or uuid.uuid4().hex[:12]
    _REQUEST_ID.set(request_id)
    return request_id


def get_request_id() -> str:
    return _REQUEST_ID.get()


def reset_request_id() -> None:
    _REQUEST_ID.set("-")


class RequestIdFilter(logging.Filter):
    """Attach the current request id to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


def configure_logging() -> None:
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
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
