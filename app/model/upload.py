"""Upload metadata and status shapes.

An upload is one submitted log file plus its processing state; the state
machine is in ``spec.md`` - "Data Model".
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UploadResponse(BaseModel):
    """Result of a successful upload."""

    id: int
    filename: str
    status: str
    event_count: int
    anomaly_count: int


class UploadStatus(BaseModel):
    """Current processing state of one upload."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    status: str
    uploaded_at: datetime
    processed_at: datetime | None = None
    event_count: int
    anomaly_count: int
    error_message: str | None = None
