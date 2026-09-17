"""Canonical event schema: the normalized shape every parsed log line becomes.

`app.service.parsing` converts each raw Zscaler NSS web-log record into one
`CanonicalEvent`. Detection rules and the timeline only ever see this shape,
never raw NSS fields. The full NSS field -> canonical field mapping table
lives in spec.md - "Log Format & Canonical Schema".
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EventBase(BaseModel):
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
    raw: dict[str, Any] = Field(default_factory=dict)


class EventOut(EventBase):
    id: int


class EventPage(BaseModel):
    items: list[EventOut]
    total: int
    limit: int
    offset: int
