"""Background job that produces and persists one upload's narrative.

Scheduled by ``POST /api/uploads/{id}/narrative`` via FastAPI BackgroundTasks
and run after the response. Opens its own session, because the request session
is already closed by then. Invariants: it never raises (every failure writes a
``failed`` row); zero-event uploads get a canned brief without a model call;
the model sees only the facts block, never raw events.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.data import repository
from app.llm.client import LlmError, NarrativeClient
from app.model.event import EventOut
from app.model.summary import AnomalyOut, SummaryResponse
from app.service.narrative import (
    JSON_SCHEMA,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    NarrativeValidationError,
    build_facts,
    empty_narrative,
    risk_level,
    validate_sections,
)
from app.service.timeline import build_summary

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Session]


def load_summary(session: Session, upload_id: int) -> SummaryResponse:
    """Same aggregation the /summary route performs, for internal use."""
    events = [
        EventOut.model_validate(row)
        for row in repository.get_events_for_summary(session, upload_id)
    ]
    timestamps = {event.id: event.timestamp for event in events}
    anomalies: list[AnomalyOut] = []
    for row in repository.get_anomalies(session, upload_id):
        anomaly = AnomalyOut.model_validate(row)
        anomaly.timestamp = (
            timestamps.get(row.event_id) if row.event_id is not None else None
        )
        anomalies.append(anomaly)
    return build_summary(upload_id, events, anomalies)


def generate_narrative(
    upload_id: int,
    client: NarrativeClient,
    session_factory: SessionFactory,
) -> None:
    """Generate, validate, and persist the narrative for one upload."""
    session = session_factory()
    try:
        summary = load_summary(session, upload_id)
        level = risk_level(summary.anomalies)

        if summary.total_events == 0:
            repository.upsert_narrative(
                session,
                upload_id,
                status="ready",
                risk_level=level,
                model="none",
                prompt_version=PROMPT_VERSION,
                content=empty_narrative().model_dump(),
                latency_ms=0,
            )
            return

        facts = build_facts(summary)
        logger.debug("narrative upload_id=%s facts=%d chars", upload_id, len(facts))

        completion = client.complete(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=facts,
            json_schema=JSON_SCHEMA,
        )
        sections = validate_sections(completion.data, facts)

        if completion.model != client.model:
            logger.info(
                "server reported model=%s, configured=%s",
                completion.model,
                client.model,
            )
        # Store the *configured* name: cache validity is checked against it.
        repository.upsert_narrative(
            session,
            upload_id,
            status="ready",
            risk_level=level,
            model=client.model,
            prompt_version=PROMPT_VERSION,
            content=sections.model_dump(),
            latency_ms=completion.latency_ms,
        )
    except (LlmError, NarrativeValidationError) as exc:
        _fail(session, upload_id, str(exc))
    except Exception:  # background task must never raise
        logger.exception("narrative upload_id=%s crashed", upload_id)
        _fail(session, upload_id, "Unexpected error while generating the summary.")
    finally:
        session.close()


def _fail(session: Session, upload_id: int, message: str) -> None:
    try:
        session.rollback()
        level = "none"
        try:
            level = risk_level(load_summary(session, upload_id).anomalies)
        except Exception:  # noqa: BLE001 - best effort; failure row still written
            logger.debug("narrative upload_id=%s risk level unavailable", upload_id)
        repository.upsert_narrative(
            session,
            upload_id,
            status="failed",
            risk_level=level,
            prompt_version=PROMPT_VERSION,
            error_message=message,
        )
    except Exception:
        logger.exception("narrative upload_id=%s could not record failure", upload_id)
