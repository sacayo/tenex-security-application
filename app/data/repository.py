"""Repository: every database read/write the rest of the app needs.

Routes call these functions; they never write SQL themselves. Keeping all
queries here means there is exactly one place to audit for injection risks.

Each function commits its own work so a failed parse still leaves an
auditable `failed` upload row (spec.md - "Data Model").
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.data.tables import Anomaly, Event, Narrative, Upload
from app.model.event import CanonicalEvent
from app.model.summary import DetectedAnomaly

logger = logging.getLogger(__name__)


def create_upload(session: Session, *, filename: str, file_size: int) -> Upload:
    """Insert an uploads row with status "parsing" and return it."""
    upload = Upload(filename=filename, file_size_bytes=file_size, status="parsing")
    session.add(upload)
    session.commit()
    logger.debug("created upload id=%s size=%d", upload.id, file_size)
    return upload


def mark_upload_completed(
    session: Session, upload_id: int, event_count: int, anomaly_count: int
) -> None:
    """Set status "completed", counts, and processed_at."""
    upload = session.get(Upload, upload_id)
    if upload is None:
        return
    upload.status = "completed"
    upload.event_count = event_count
    upload.anomaly_count = anomaly_count
    upload.processed_at = datetime.now(UTC)
    session.commit()
    logger.info(
        "upload id=%s completed events=%d anomalies=%d",
        upload_id,
        event_count,
        anomaly_count,
    )


def mark_upload_failed(session: Session, upload_id: int, error_message: str) -> None:
    """Set status "failed" + error_message (route's except path)."""
    upload = session.get(Upload, upload_id)
    if upload is None:
        return
    upload.status = "failed"
    upload.error_message = error_message
    upload.processed_at = datetime.now(UTC)
    session.commit()
    logger.warning("upload id=%s failed: %s", upload_id, error_message)


def insert_events(
    session: Session, upload_id: int, events: list[CanonicalEvent]
) -> list[Event]:
    """Bulk-insert normalized events; returns rows (with ids) in input order."""
    rows = [
        Event(
            upload_id=upload_id,
            timestamp=event.timestamp,
            client_ip=event.client_ip,
            username=event.username,
            method=event.method,
            url=event.url,
            host=event.host,
            status_code=event.status_code,
            action=event.action,
            url_category=event.url_category,
            threat_name=event.threat_name,
            risk_score=event.risk_score,
            bytes_sent=event.bytes_sent,
            bytes_received=event.bytes_received,
            user_agent=event.user_agent,
            dlp_dictionary=event.dlp_dictionary,
            raw=event.raw,
        )
        for event in events
    ]
    session.add_all(rows)
    session.commit()
    logger.debug("inserted %d event(s) for upload id=%s", len(rows), upload_id)
    return rows


def insert_anomalies(
    session: Session,
    upload_id: int,
    anomalies: list[DetectedAnomaly],
    event_ids: list[int],
) -> None:
    """Persist anomalies, mapping each `event_index` to the real events.id."""
    rows: list[Anomaly] = []
    for anomaly in anomalies:
        event_id = (
            event_ids[anomaly.event_index] if anomaly.event_index is not None else None
        )
        rows.append(
            Anomaly(
                upload_id=upload_id,
                event_id=event_id,
                rule=anomaly.rule,
                severity=anomaly.severity,
                title=anomaly.title,
                description=anomaly.description,
            )
        )
    session.add_all(rows)
    session.commit()
    logger.debug("inserted %d anomaly(ies) for upload id=%s", len(rows), upload_id)


def get_upload(session: Session, upload_id: int) -> Upload | None:
    return session.get(Upload, upload_id)


def list_events(
    session: Session,
    upload_id: int,
    *,
    limit: int,
    offset: int,
    action: str | None = None,
    url_category: str | None = None,
    anomalies_only: bool = False,
) -> tuple[list[Event], int]:
    """Return one page of events plus the total matching count."""
    filters = [Event.upload_id == upload_id]
    if action is not None:
        filters.append(Event.action == action)
    if url_category is not None:
        filters.append(Event.url_category == url_category)
    if anomalies_only:
        flagged_event_ids = select(Anomaly.event_id).where(
            Anomaly.upload_id == upload_id, Anomaly.event_id.is_not(None)
        )
        filters.append(Event.id.in_(flagged_event_ids))

    total = session.scalar(select(func.count()).select_from(Event).where(*filters)) or 0
    statement = (
        select(Event)
        .where(*filters)
        .order_by(Event.timestamp, Event.id)
        .limit(limit)
        .offset(offset)
    )
    items = list(session.scalars(statement).all())
    logger.debug(
        "listed %d/%d event(s) for upload id=%s (offset=%d)",
        len(items),
        total,
        upload_id,
        offset,
    )
    return items, total


def get_events_for_summary(session: Session, upload_id: int) -> list[Event]:
    statement = (
        select(Event)
        .where(Event.upload_id == upload_id)
        .order_by(Event.timestamp, Event.id)
    )
    return list(session.scalars(statement).all())


def get_anomalies(session: Session, upload_id: int) -> list[Anomaly]:
    statement = (
        select(Anomaly).where(Anomaly.upload_id == upload_id).order_by(Anomaly.id)
    )
    return list(session.scalars(statement).all())


# --------------------------------------------------------------------------
# Narratives (LLM brief cache)
# --------------------------------------------------------------------------


def get_narrative(session: Session, upload_id: int) -> Narrative | None:
    return session.scalar(select(Narrative).where(Narrative.upload_id == upload_id))


def mark_narrative_pending(session: Session, upload_id: int) -> Narrative:
    """Create or reset the row to "pending" before scheduling generation.

    Clears the previous content so a refresh never serves stale text with a
    pending status; the frontend shows a skeleton until the new brief lands.
    """
    row = get_narrative(session, upload_id)
    if row is None:
        row = Narrative(upload_id=upload_id)
        session.add(row)
    row.status = "pending"
    row.content = None
    row.error_message = None
    row.latency_ms = None
    row.updated_at = datetime.now(UTC)
    session.commit()
    logger.debug("narrative upload_id=%s -> pending", upload_id)
    return row


def upsert_narrative(
    session: Session,
    upload_id: int,
    *,
    status: str,
    risk_level: str,
    model: str | None = None,
    prompt_version: str | None = None,
    content: dict | None = None,
    error_message: str | None = None,
    latency_ms: int | None = None,
) -> Narrative:
    """Write the terminal state of a generation run ("ready" or "failed")."""
    row = get_narrative(session, upload_id)
    if row is None:
        row = Narrative(upload_id=upload_id)
        session.add(row)
    row.status = status
    row.risk_level = risk_level
    row.model = model
    row.prompt_version = prompt_version
    row.content = content
    row.error_message = error_message
    row.latency_ms = latency_ms
    row.updated_at = datetime.now(UTC)
    session.commit()
    if status == "ready":
        logger.info(
            "narrative upload_id=%s ready model=%s latency=%sms",
            upload_id,
            model,
            latency_ms,
        )
    else:
        logger.warning("narrative upload_id=%s failed: %s", upload_id, error_message)
    return row
