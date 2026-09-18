"""Shapes for the results-page summary.

``GET /api/uploads/{id}/summary`` returns one ``SummaryResponse``; the frontend
renders it 1:1, so update ``spec.md`` and ``web/lib/types.ts`` together.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

Severity = Literal["low", "medium", "high"]


class DetectedAnomaly(BaseModel):
    """An anomaly from detection, keyed by the event's list index."""

    rule: str
    severity: Severity
    title: str
    description: str
    event_index: int | None = None


class TimelineBucket(BaseModel):
    """Counts for one time bucket of the timeline."""

    bucket_start: datetime
    event_count: int
    blocked_count: int
    anomaly_count: int


class AnomalyOut(BaseModel):
    """A persisted anomaly as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    rule: str
    severity: Severity
    title: str
    description: str
    event_id: int | None = None
    timestamp: datetime | None = None


class CategoryCount(BaseModel):
    """A URL category and its event count."""

    category: str
    count: int


class HostCount(BaseModel):
    """A destination host and its event count."""

    host: str
    count: int


class SummaryResponse(BaseModel):
    """Everything the results page needs in one payload."""

    upload_id: int
    time_range_start: datetime
    time_range_end: datetime
    total_events: int
    unique_clients: int
    unique_users: int
    blocked_count: int
    allowed_count: int
    top_categories: list[CategoryCount]
    top_hosts: list[HostCount]
    timeline: list[TimelineBucket]
    anomalies: list[AnomalyOut]
