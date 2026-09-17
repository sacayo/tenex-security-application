"""Upload metadata shapes.

An "upload" is one user-submitted log file plus its processing state.
The state machine is defined in spec.md - "Data Model":

    uploaded -> parsing -> completed
                parsing -> failed   (error_message set)
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UploadResponse(BaseModel):
    id: int
    filename: str
    status: str
    event_count: int
    anomaly_count: int


class UploadStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    status: str
    uploaded_at: datetime
    processed_at: datetime | None = None
    event_count: int
    anomaly_count: int
    error_message: str | None = None
