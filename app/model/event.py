"""Canonical event schema.

``app.service.parsing`` maps each raw NSS web-log record to one
``CanonicalEvent``; detection and the timeline only ever see this shape. The
NSS field mapping is in ``spec.md`` - "Log Format & Canonical Schema".
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EventBase(BaseModel):
    """Canonical fields shared by the parsed and API event shapes."""

    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    client_ip: str
    username: str | None = None
    method: str | None = None
    url: str
    host: str | None = None
    status_code: int | None = None
    action: str
    url_category: str | None = None
    threat_name: str | None = None
    risk_score: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    user_agent: str | None = None
    dlp_dictionary: str | None = None


class CanonicalEvent(EventBase):
    """A parsed event plus its untouched raw NSS record."""

    raw: dict[str, Any] = Field(default_factory=dict)


class EventOut(EventBase):
    """A persisted event as returned by the API."""

    id: int


class EventPage(BaseModel):
    """One page of events plus paging metadata."""

    items: list[EventOut]
    total: int
    limit: int
    offset: int
