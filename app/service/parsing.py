"""Log parsing pipeline: raw NSS web-log bytes -> list[CanonicalEvent].

Format is detected from content, not the file extension: a JSON array or
object, NDJSON, or delimited text (CSV/TSV/pipe) in the Zscaler default
"NSS Feed Output Format: Web Logs" layout, with or without a header row.
Field mapping and gotchas: ``spec.md`` - "Log Format & Canonical Schema".
"""

from __future__ import annotations

import csv
import io
import json
import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import unquote, urlparse

from app.model.event import CanonicalEvent

logger = logging.getLogger(__name__)

_SENTINELS = frozenset({"", "None", "N/A", "NA", "n/a", "na"})
_TIME_FORMATS = (
    "%a %b %d %Y %H:%M:%S",  # JSON feed: "Thu Sep 10 2026 09:15:23"
    "%a %b %d %H:%M:%S %Y",  # CSV feed:  "Mon Jun 20 15:29:11 2022"
)

# Zscaler default "NSS Feed Output Format: Web Logs", positional order.
# See https://help.zscaler.com/zia/nss-feed-output-format-web-logs
_CSV_COLUMNS = (
    "time",
    "login",
    "proto",
    "eurl",
    "action",
    "appname",
    "appclass",
    "reqsize",
    "respsize",
    "stime",
    "ctime",
    "urlclass",
    "urlsupercat",
    "urlcat",
    "malwarecat",
    "threatname",
    "riskscore",
    "dlpeng",
    "dlpdict",
    "location",
    "dept",
    "cip",
    "sip",
    "reqmethod",
    "respcode",
    "ua",
    "ereferer",
    "ruletype",
    "rulelabel",
    "contenttype",
    "unscannabletype",
    "deviceowner",
    "devicehostname",
    "devicemodel",
)

_ACTION_MAP = {
    "block": "Block",
    "blocked": "Block",
    "allow": "Allow",
    "allowed": "Allow",
}


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text in _SENTINELS:
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


def _normalize_action(value: str) -> str:
    return _ACTION_MAP.get(value.strip().lower(), value.strip())


def _try_parse_time(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    for fmt in _TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_time(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"invalid timestamp: {value!r}")
    parsed = _try_parse_time(value)
    if parsed is None:
        raise ValueError(f"unparseable timestamp: {value!r}")
    return parsed


def _host_from_url(url: str) -> str | None:
    """Derive a hostname from eurl when ehost is absent (CSV default feed)."""
    candidate = url.strip()
    if not candidate:
        return None
    if "://" not in candidate:
        candidate = f"//{candidate}"
    parsed = urlparse(candidate)
    host = parsed.hostname or parsed.path.split("/")[0] or None
    return host


def _to_event(record: dict[str, Any]) -> CanonicalEvent:
    host = _clean(record.get("ehost"))
    url = unquote(_required(record, "eurl"))
    if host is None:
        host = _host_from_url(url)
    else:
        host = unquote(host)
    status_code = _clean(record.get("respcode"))
    return CanonicalEvent(
        timestamp=_parse_time(record.get("time")),
        client_ip=_required(record, "cip"),
        username=_clean(record.get("login")),
        method=_clean(record.get("reqmethod")),
        url=url,
        host=host,
        status_code=int(status_code) if status_code is not None else None,
        action=_normalize_action(_required(record, "action")),
        url_category=_clean(record.get("urlcat")),
        threat_name=_clean(record.get("threatname")),
        risk_score=_to_int(record.get("riskscore")),
        bytes_sent=_to_int(record.get("reqsize")),
        bytes_received=_to_int(record.get("respsize")),
        user_agent=_clean(record.get("ua")),
        dlp_dictionary=_clean(record.get("dlpdict")),
        raw=record,
    )


def _iter_json_records(text: str) -> tuple[list[Any], int] | None:
    """Return (records, malformed) if the payload looks like JSON/NDJSON, else None."""
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError:
        records: list[Any] = []
        malformed = 0
        saw_object = False
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(json.loads(stripped))
                saw_object = True
            except json.JSONDecodeError:
                malformed += 1
        if not saw_object:
            return None
        return records, malformed
    if isinstance(loaded, dict):
        return [loaded], 0
    if isinstance(loaded, list):
        return loaded, 0
    return [], 1


def _sniff_delimiter(sample: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t|")
        return dialect.delimiter
    except csv.Error:
        return ","


def _row_to_record(
    cells: list[str], columns: tuple[str, ...] | list[str]
) -> dict[str, str] | None:
    if len(cells) != len(columns):
        return None
    return {col: cell for col, cell in zip(columns, cells, strict=True)}


def _iter_delimited_records(text: str) -> tuple[list[dict[str, str]], int]:
    sample = "\n".join(text.splitlines()[:5])
    delimiter = _sniff_delimiter(sample) if sample.strip() else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        return [], 0

    first = rows[0]
    first_cell = first[0].strip() if first else ""
    looks_like_header = _try_parse_time(first_cell) is None and (
        first_cell.lower() in {"time", "datetime", "timestamp"}
        or any(
            c.strip().lower() in {"cip", "eurl", "action", "login", "time"}
            for c in first
        )
    )

    if looks_like_header:
        columns = [c.strip().lower() for c in first]
        data_rows = rows[1:]
    else:
        columns = list(_CSV_COLUMNS)
        data_rows = rows

    records: list[dict[str, str]] = []
    malformed = 0
    for row in data_rows:
        if len(row) != len(columns):
            malformed += 1
            continue
        record = _row_to_record(row, columns)
        if record is None:
            malformed += 1
            continue
        records.append(record)
    return records, malformed


def _iter_records(text: str) -> tuple[list[Any], int]:
    json_result = _iter_json_records(text)
    if json_result is not None:
        return json_result
    return _iter_delimited_records(text)


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
        raise ValueError(
            "Unrecognized content: expected NSS web-log JSON, NDJSON, "
            "or delimited (CSV/TSV) output."
        )

    logger.info("parsed %d event(s), skipped %d", len(events), skipped)
    return events
