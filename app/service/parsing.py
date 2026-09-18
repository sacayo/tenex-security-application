"""Log parsing pipeline: raw NSS web-log bytes -> list[CanonicalEvent].

Input format: Zscaler "NSS Feed Output Format: Web Logs" with the JSON feed
output type. A file is EITHER a JSON array of record objects OR newline-
delimited JSON (one record per line) - support both. Field mapping and all
format gotchas (hex-escaped URLs, "None" sentinels, timestamp formats) are
documented in spec.md - "Log Format & Canonical Schema".
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import unquote

from app.model.event import CanonicalEvent

logger = logging.getLogger(__name__)

_SENTINEL = "None"
_TIME_FORMAT = "%a %b %d %Y %H:%M:%S"


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    if text == "" or text == _SENTINEL:
        return None
    return text


def _required(record: dict[str, Any], key: str) -> str:
    value = _clean(record.get(key))
    if value is None:
        raise ValueError(f"missing required field: {key}")
    return value


def _to_int(value: Any, default: int = 0) -> int:
    text = _clean(value)
    if text is None:
        return default
    return int(text)


def _parse_time(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"invalid timestamp: {value!r}")
    try:
        return datetime.strptime(value.strip(), _TIME_FORMAT).replace(tzinfo=UTC)
    except ValueError as exc:
        raise ValueError(f"unparseable timestamp: {value!r}") from exc


def _iter_records(text: str) -> tuple[list[Any], int]:
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError:
        records: list[Any] = []
        malformed = 0
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(json.loads(stripped))
            except json.JSONDecodeError:
                malformed += 1
        return records, malformed
    if isinstance(loaded, dict):
        return [loaded], 0
    if isinstance(loaded, list):
        return loaded, 0
    return [], 1


def _to_event(record: dict[str, Any]) -> CanonicalEvent:
    host = _clean(record.get("ehost"))
    status_code = _clean(record.get("respcode"))
    return CanonicalEvent(
        timestamp=_parse_time(record.get("time")),
        client_ip=_required(record, "cip"),
        username=_clean(record.get("login")),
        method=_clean(record.get("reqmethod")),
        url=unquote(_required(record, "eurl")),
        host=unquote(host) if host is not None else None,
        status_code=int(status_code) if status_code is not None else None,
        action=_required(record, "action"),
        url_category=_clean(record.get("urlcat")),
        threat_name=_clean(record.get("threatname")),
        risk_score=_to_int(record.get("riskscore")),
        bytes_sent=_to_int(record.get("reqsize")),
        bytes_received=_to_int(record.get("respsize")),
        user_agent=_clean(record.get("ua")),
        dlp_dictionary=_clean(record.get("dlpdict")),
        raw=record,
    )


def parse_nss_feed(raw: bytes) -> list[CanonicalEvent]:
    """Parse a whole uploaded file into normalized canonical events."""
    text = raw.decode("utf-8", errors="replace")
    if not text.strip():
        logger.warning("empty upload: no bytes to parse")
        raise ValueError("Empty file: no log records found.")

    records, skipped = _iter_records(text)
    events: list[CanonicalEvent] = []
    for record in records:
        if not isinstance(record, dict):
            skipped += 1
            continue
        try:
            events.append(_to_event(record))
        except (KeyError, TypeError, ValueError) as exc:
            skipped += 1
            logger.debug("skipping malformed record: %s", exc)

    if skipped:
        logger.warning("skipped %d malformed record(s)", skipped)

    if not events:
        logger.warning("no valid records found in upload")
        raise ValueError("Unrecognized content: not valid NSS web-log JSON.")

    logger.info("parsed %d event(s), skipped %d", len(events), skipped)
    return events
