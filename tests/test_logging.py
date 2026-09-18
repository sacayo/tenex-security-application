"""Tests for the logging setup: correlation ids, skip warnings, and the
negative guarantee that INFO/DEBUG logs never leak secrets or usernames.
"""

import json
import logging
from pathlib import Path

from fastapi.testclient import TestClient

from app.data.session import DATABASE_URL, log_engine_target
from app.log_config import RequestIdFilter, reset_request_id, set_request_id
from app.main import app
from app.service.parsing import parse_nss_feed

FIXTURE = Path(__file__).parent / "fixtures" / "sample_nss_web.json"

client = TestClient(app)


def _records() -> list[dict]:
    return json.loads(FIXTURE.read_text())


def test_request_id_filter_injects_current_id() -> None:
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "msg", None, None)
    set_request_id("abc123")
    try:
        RequestIdFilter().filter(record)
        assert record.request_id == "abc123"
    finally:
        reset_request_id()


def test_request_id_header_is_returned() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")


def test_request_line_is_logged(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="app.main"):
        client.get("/health")
    assert "GET /health" in caplog.text


def test_parser_warns_when_records_are_skipped(caplog) -> None:
    records = _records()
    records.append({"time": "Thu Sep 10 2026 09:00:00", "eurl": "http://x"})
    with caplog.at_level(logging.WARNING):
        events = parse_nss_feed(json.dumps(records).encode())
    assert len(events) == 6
    assert "skipped" in caplog.text.lower()


def test_parser_logs_counts_at_info(caplog) -> None:
    with caplog.at_level(logging.INFO):
        parse_nss_feed(FIXTURE.read_bytes())
    assert "parsed 6 event" in caplog.text


def test_parsing_logs_do_not_include_usernames(caplog) -> None:
    with caplog.at_level(logging.DEBUG):
        parse_nss_feed(FIXTURE.read_bytes())
    assert "alice.smith" not in caplog.text
    assert "carol.davis" not in caplog.text


def test_engine_log_does_not_expose_credentials(caplog) -> None:
    from sqlalchemy.engine import make_url

    url = make_url(DATABASE_URL)
    with caplog.at_level(logging.DEBUG):
        log_engine_target()
    assert "engine target" in caplog.text
    if url.username and url.password:
        assert f"{url.username}:{url.password}" not in caplog.text
