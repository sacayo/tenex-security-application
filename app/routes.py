"""HTTP layer: the REST API surface.

Each handler stays *thin*: validate input -> call into `app.service` /
`app.data.repository` -> return shapes defined in `app.model`. No parsing,
detection, or SQL in this file.

Contract: spec.md - "API Contract". The frontend in `web/` is built against
it, so do not deviate without updating spec.md and `web/lib/api.ts`.
"""

import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.data import repository
from app.data.session import get_session
from app.model.event import EventOut, EventPage
from app.model.summary import AnomalyOut, SummaryResponse
from app.model.upload import UploadResponse, UploadStatus
from app.service.detection import run_rules
from app.service.parsing import parse_nss_feed
from app.service.timeline import build_summary

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = {".json", ".jsonl", ".ndjson", ".log", ".txt", ".csv", ".tsv"}
MAX_EVENT_LIMIT = 200

SessionDep = Annotated[Session, Depends(get_session)]


@router.post("/logs", status_code=201)
async def upload_log(
    file: UploadFile,
    session: SessionDep,
) -> UploadResponse:
    """Accept an NSS web-log file, parse it, detect, and persist everything."""
    filename = file.filename or "upload.log"
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        logger.warning("rejected upload: unsupported extension %r", extension)
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{extension}'. "
                "Use .json, .jsonl, .ndjson, .log, .txt, .csv, or .tsv."
            ),
        )

    data = await file.read()
    if not data:
        logger.warning("rejected upload: empty file")
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(data) > MAX_UPLOAD_BYTES:
        logger.warning("rejected upload: %d bytes exceeds cap", len(data))
        raise HTTPException(status_code=413, detail="File exceeds the 25 MB limit.")

    upload = repository.create_upload(
        session, filename=filename, file_size=len(data)
    )

    try:
        events = parse_nss_feed(data)
        anomalies = run_rules(events)
        rows = repository.insert_events(session, upload.id, events)
        event_ids = [row.id for row in rows]
        repository.insert_anomalies(session, upload.id, anomalies, event_ids)
        repository.mark_upload_completed(
            session, upload.id, len(events), len(anomalies)
        )
    except ValueError as exc:
        repository.mark_upload_failed(session, upload.id, str(exc))
        logger.warning("upload id=%s rejected: %s", upload.id, exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return UploadResponse(
        id=upload.id,
        filename=upload.filename,
        status="completed",
        event_count=len(events),
        anomaly_count=len(anomalies),
    )


@router.get("/uploads/{upload_id}")
def get_upload(
    upload_id: int,
    session: SessionDep,
) -> UploadStatus:
    """Return metadata/processing status for one upload."""
    upload = repository.get_upload(session, upload_id)
    if upload is None:
        logger.warning("upload id=%s not found", upload_id)
        raise HTTPException(status_code=404, detail="Upload not found.")
    return UploadStatus.model_validate(upload)


@router.get("/uploads/{upload_id}/events")
def list_events(
    upload_id: int,
    session: SessionDep,
    limit: int = Query(50, ge=1),
    offset: int = Query(0, ge=0),
    action: str | None = None,
    url_category: str | None = None,
    anomalies_only: bool = False,
) -> EventPage:
    """Return a page of normalized events for one upload."""
    if repository.get_upload(session, upload_id) is None:
        raise HTTPException(status_code=404, detail="Upload not found.")

    effective_limit = min(limit, MAX_EVENT_LIMIT)
    rows, total = repository.list_events(
        session,
        upload_id,
        limit=effective_limit,
        offset=offset,
        action=action,
        url_category=url_category,
        anomalies_only=anomalies_only,
    )
    return EventPage(
        items=[EventOut.model_validate(row) for row in rows],
        total=total,
        limit=effective_limit,
        offset=offset,
    )


@router.get("/uploads/{upload_id}/summary")
def get_summary(
    upload_id: int,
    session: SessionDep,
) -> SummaryResponse:
    """Return the human-readable summary + timeline the frontend renders."""
    if repository.get_upload(session, upload_id) is None:
        raise HTTPException(status_code=404, detail="Upload not found.")

    events = [
        EventOut.model_validate(row)
        for row in repository.get_events_for_summary(session, upload_id)
    ]
    timestamps = {event.id: event.timestamp for event in events}
    anomalies = []
    for row in repository.get_anomalies(session, upload_id):
        anomaly = AnomalyOut.model_validate(row)
        anomaly.timestamp = (
            timestamps.get(row.event_id) if row.event_id is not None else None
        )
        anomalies.append(anomaly)

    return build_summary(upload_id, events, anomalies)
