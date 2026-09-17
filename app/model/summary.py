"""Summary shapes: what the frontend needs to render the results page.

GET /api/uploads/{id}/summary returns one `SummaryResponse`. The frontend
(`web/` results page) renders these shapes 1:1 - if you change them, update
spec.md and `web/lib/types.ts` together.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

Severity = Literal["low", "medium", "high"]


class DetectedAnomaly(BaseModel):
    rule: str
    severity: Severity
    title: str
    description: str
    event_index: int | None = None


class TimelineBucket(BaseModel):
    bucket_start: datetime
    event_count: int
    blocked_count: int
    anomaly_count: int


class AnomalyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule: str
    severity: Severity
    title: str
    description: str
    event_id: int | None = None
    timestamp: datetime | None = None


class CategoryCount(BaseModel):
    category: str
    count: int


class HostCount(BaseModel):
    host: str
    count: int


class SummaryResponse(BaseModel):
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
