"""Upload metadata shapes.

An "upload" is one user-submitted log file plus its processing state.
The state machine is defined in spec.md - "Data Model":

    uploaded -> parsing -> completed
                parsing -> failed   (error_message set)
"""

from pydantic import BaseModel


class UploadResponse(BaseModel):
    """Returned by POST /api/logs (201) once processing finished.

    TODO(spec.md - "API Contract"): fields -
        id: int
        filename: str
        status: str
        event_count: int
        anomaly_count: int
    """


class UploadStatus(BaseModel):
    """Returned by GET /api/uploads/{id}.

    TODO: fields - id, filename, status, uploaded_at: datetime,
    processed_at: datetime | None, event_count: int, anomaly_count: int,
    error_message: str | None.
    """
