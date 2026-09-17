"""Summary shapes: what the frontend needs to render the results page.

GET /api/uploads/{id}/summary returns one `SummaryResponse`. The frontend
(`web/` results page) renders these shapes 1:1 - if you change them, update
spec.md and `web/lib/types.ts` together.
"""

from pydantic import BaseModel


class DetectedAnomaly(BaseModel):
    """What a detection rule emits, BEFORE anything is stored in the database.

    TODO: fields - rule: str, severity: str ("low" | "medium" | "high"),
    title: str, description: str,
    event_index: int | None  # index into the parsed events list, if the
                             # anomaly points at one specific event
    """


class TimelineBucket(BaseModel):
    """One time slice of the timeline chart.

    TODO: fields - bucket_start: datetime, event_count: int,
    blocked_count: int, anomaly_count: int.
    """


class AnomalyOut(BaseModel):
    """One detected anomaly as shown in the UI.

    TODO: fields - id: int, rule: str (rule name, e.g. "threat-detected"),
    severity: str ("low" | "medium" | "high"), title: str,
    description: str, event_id: int | None, timestamp: datetime | None.
    """


class SummaryResponse(BaseModel):
    """The whole results page in one response.

    TODO(spec.md - "API Contract"): fields -
        upload_id: int
        time_range_start: datetime
        time_range_end: datetime
        total_events: int
        unique_clients: int          # distinct client_ip
        unique_users: int            # distinct username
        blocked_count: int
        allowed_count: int
        top_categories: list[...]    # e.g. {"category": str, "count": int}
        top_hosts: list[...]         # e.g. {"host": str, "count": int}
        timeline: list[TimelineBucket]
        anomalies: list[AnomalyOut]

    Tip: define tiny helper models (e.g. CategoryCount, HostCount) for the
    top-* lists instead of loose dicts.
    """
