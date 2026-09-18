"""Tests for app.service.parsing.

Covers: happy path (JSON array + NDJSON), field mapping/typing, UTC
timestamps, hex-escaped URLs, "None" sentinels, malformed-record skipping,
and the two fatal cases (empty file, unrecognizable content).
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.service.parsing import parse_nss_feed

FIXTURE = Path(__file__).parent / "fixtures" / "sample_nss_web.json"
CSV_FIXTURE = Path(__file__).parent / "fixtures" / "sample_nss_csv.txt"


def _fixture_records() -> list[dict]:
    return json.loads(FIXTURE.read_text())


def test_parse_json_array_fixture() -> None:
    events = parse_nss_feed(FIXTURE.read_bytes())
    assert len(events) == 6
    assert events[0].client_ip == "10.1.2.15"


def test_parse_ndjson_variant() -> None:
    records = _fixture_records()
    ndjson = "\n".join(json.dumps(record) for record in records).encode()
    events = parse_nss_feed(ndjson)
    assert len(events) == 6
    assert events[0].client_ip == "10.1.2.15"


def test_field_mapping_and_types() -> None:
    events = parse_nss_feed(FIXTURE.read_bytes())
    first = events[0]
    assert first.username == "alice.smith"
    assert first.method == "GET"
    assert first.host == "www.google.com"
    assert first.action == "Allow"
    assert first.url_category == "Search Engines"
    assert isinstance(first.status_code, int)
    assert first.status_code == 200
    assert isinstance(first.risk_score, int)
    assert first.risk_score == 5
    assert first.bytes_sent == 512
    assert first.bytes_received == 18432
    assert events[3].bytes_sent == 26214400


def test_timestamps_are_timezone_aware_utc() -> None:
    events = parse_nss_feed(FIXTURE.read_bytes())
    assert events[0].timestamp.tzinfo is not None
    assert events[0].timestamp == datetime(2026, 9, 10, 9, 15, 23, tzinfo=UTC)


def test_hex_escaped_url_is_decoded() -> None:
    events = parse_nss_feed(FIXTURE.read_bytes())
    assert events[0].url == "https://www.google.com/search?q=standup notes"


def test_none_sentinels_become_none() -> None:
    events = parse_nss_feed(FIXTURE.read_bytes())
    assert events[5].username is None
    assert events[0].threat_name is None
    assert events[0].dlp_dictionary is None
    assert events[5].user_agent is None
    assert events[2].threat_name == "Trojan.Win32.FakeAV"
    assert events[4].dlp_dictionary == "Credit Cards"


def test_raw_record_is_preserved() -> None:
    events = parse_nss_feed(FIXTURE.read_bytes())
    assert events[0].raw["recordid"] == "700001"


def test_malformed_line_is_skipped() -> None:
    records = _fixture_records()
    ndjson = "\n".join(json.dumps(record) for record in records)
    payload = f"{ndjson}\nnot-json-at-all\n".encode()
    events = parse_nss_feed(payload)
    assert len(events) == 6


def test_record_missing_required_field_is_skipped() -> None:
    records = _fixture_records()
    records.append({"time": "Thu Sep 10 2026 09:00:00", "eurl": "http://x"})
    events = parse_nss_feed(json.dumps(records).encode())
    assert len(events) == 6


def test_unrecognizable_content_raises() -> None:
    with pytest.raises(ValueError):
        parse_nss_feed(b"this is not json at all")


def test_empty_file_raises() -> None:
    with pytest.raises(ValueError):
        parse_nss_feed(b"")


def test_csv_nss_output_is_rejected() -> None:
    with pytest.raises(ValueError):
        parse_nss_feed(CSV_FIXTURE.read_bytes())
