"""HTTP layer: the REST API surface.

Handlers stay thin: validate input, call ``app.service`` /
``app.data.repository``, and return ``app.model`` shapes. No parsing,
detection, or SQL here. Contract: ``spec.md`` - "API Contract"; keep
``web/lib/api.ts`` in sync.
"""

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.config import get_settings
from app.data import repository
from app.data.session import factory_for, get_session
from app.data.tables import Narrative
from app.llm.client import NarrativeClient, get_llm_client
from app.llm.generate import generate_narrative, load_summary
from app.model.event import EventOut, EventPage
from app.model.narrative import NarrativeResponse
from app.model.summary import SummaryResponse
from app.model.upload import UploadResponse, UploadStatus
from app.service.detection import run_rules
from app.service.narrative import PROMPT_VERSION
from app.service.parsing import parse_nss_feed

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = {".json", ".jsonl", ".ndjson", ".log", ".txt", ".csv", ".tsv"}
MAX_EVENT_LIMIT = 200
# A "pending" narrative older than the LLM timeout plus this grace is
# assumed orphaned (process restarted mid-generation) and treated as failed.
STUCK_GRACE_SECONDS = 60

SessionDep = Annotated[Session, Depends(get_session)]
LlmDep = Annotated[NarrativeClient | None, Depends(get_llm_client)]


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

    upload = repository.create_upload(session, filename=filename, file_size=len(data))

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
    return load_summary(session, upload_id)


# --------------------------------------------------------------------------
# Narrative (LLM brief) - spec.md "LLM narrative layer"
# --------------------------------------------------------------------------


def _narrative_response(row: Narrative) -> NarrativeResponse:
    return NarrativeResponse(
        upload_id=row.upload_id,
        status=row.status,  # type: ignore[arg-type]
        risk_level=row.risk_level,  # type: ignore[arg-type]
        sections=row.content if row.status == "ready" else None,
        model=row.model,
        prompt_version=row.prompt_version,
        generated_at=row.updated_at if row.status == "ready" else None,
        error_message=row.error_message,
    )


def _age_seconds(row: Narrative, now: datetime) -> float:
    updated = row.updated_at
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=UTC)
    return (now - updated).total_seconds()


def _is_stuck(row: Narrative, now: datetime) -> bool:
    if row.status != "pending":
        return False
    limit = get_settings().llm_timeout_seconds + STUCK_GRACE_SECONDS
    return _age_seconds(row, now) > limit


def _cache_valid(row: Narrative, client: NarrativeClient) -> bool:
    """Ready rows are reusable only if produced by the same prompt + model.

    "none" is the sentinel for the canned zero-event brief, which does not
    depend on the model.
    """
    return (
        row.status == "ready"
        and row.prompt_version == PROMPT_VERSION
        and row.model in (client.model, "none")
    )


@router.post("/uploads/{upload_id}/narrative")
def request_narrative(
    upload_id: int,
    session: SessionDep,
    client: LlmDep,
    background_tasks: BackgroundTasks,
    response: Response,
    refresh: bool = False,
) -> NarrativeResponse:
    """Idempotently request an LLM brief for a completed upload.

    Status codes: 200 cached brief (ready or failed) | 202 generation in
    progress (newly scheduled or already running) | 404 unknown upload |
    409 upload not completed | 429 refresh inside cooldown | 503 LLM
    disabled. The frontend hides the card on 503.
    """
    upload = repository.get_upload(session, upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload not found.")
    if client is None:
        raise HTTPException(
            status_code=503, detail="Narrative generation is not enabled."
        )
    if upload.status != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Upload is '{upload.status}'; a narrative needs a completed upload.",
        )

    settings = get_settings()
    now = datetime.now(UTC)
    row = repository.get_narrative(session, upload_id)

    if row is not None:
        if row.status == "pending" and not _is_stuck(row, now):
            # Already running (duplicate tab, React double-mount): do not
            # schedule a second job.
            response.status_code = 202
            return _narrative_response(row)

        if row.status == "pending":
            logger.warning(
                "narrative upload_id=%s stuck pending; regenerating", upload_id
            )
        elif not refresh:
            # Serve the cached outcome, including a "failed" one: the card
            # shows the error and offers Retry (which sends refresh=true).
            if row.status == "failed" or _cache_valid(row, client):
                return _narrative_response(row)
            logger.info(
                "narrative upload_id=%s cache invalid (prompt/model); regenerating",
                upload_id,
            )
        elif _age_seconds(row, now) < settings.llm_refresh_cooldown_seconds:
            raise HTTPException(
                status_code=429,
                detail="A summary was generated recently. Try again in a few minutes.",
            )

    row, acquired = repository.claim_narrative_generation(
        session,
        upload_id,
        reclaim_stuck_before=now
        - timedelta(seconds=settings.llm_timeout_seconds + STUCK_GRACE_SECONDS),
    )
    if acquired:
        # The request session closes before the task runs; hand it a factory
        # bound to the same engine (keeps the test-DB override working).
        background_tasks.add_task(
            generate_narrative, upload_id, client, factory_for(session)
        )
        logger.info("narrative upload_id=%s scheduled refresh=%s", upload_id, refresh)
    response.status_code = 202
    return _narrative_response(row)


@router.get("/uploads/{upload_id}/narrative")
def get_narrative(
    upload_id: int,
    session: SessionDep,
) -> NarrativeResponse:
    """Return the cached brief. Body `status` is the signal to poll on."""
    if repository.get_upload(session, upload_id) is None:
        raise HTTPException(status_code=404, detail="Upload not found.")
    row = repository.get_narrative(session, upload_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Narrative not requested yet.")

    if _is_stuck(row, datetime.now(UTC)):
        logger.warning(
            "narrative upload_id=%s stuck pending; marking failed", upload_id
        )
        row = repository.upsert_narrative(
            session,
            upload_id,
            status="failed",
            risk_level=row.risk_level,
            prompt_version=row.prompt_version,
            error_message="Generation timed out. Try again.",
        )
    return _narrative_response(row)
