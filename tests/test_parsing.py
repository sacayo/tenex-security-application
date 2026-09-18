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
    with pytest.raises(ValueError, match="Unrecognized content"):
        parse_nss_feed(b"this is not json at all")


def test_empty_file_raises() -> None:
    with pytest.raises(ValueError):
        parse_nss_feed(b"")


def test_csv_default_feed_parses() -> None:
    events = parse_nss_feed(CSV_FIXTURE.read_bytes())
    assert len(events) == 1
    event = events[0]
    assert event.client_ip == "172.17.3.49"
    assert event.action == "Block"
    assert event.status_code == 403
    assert event.host == "ebay.com"
    assert event.url_category == "Online Shopping"
    assert event.bytes_sent == 72
    assert event.risk_score == 0
    assert event.timestamp == datetime(2022, 6, 20, 15, 29, 11, tzinfo=UTC)
    assert event.username == "new-gre"
    assert event.method == "GET"
    assert event.user_agent == "curl/7.68.0"
    assert event.threat_name is None
    assert event.dlp_dictionary is None
    assert event.raw["appname"] == "Ebay"


def test_csv_with_header_row() -> None:
    header = (
        "time,login,cip,eurl,action,reqmethod,respcode,urlcat,"
        "threatname,riskscore,reqsize,respsize,ua,dlpdict"
    )
    row = (
        '"Thu Sep 10 2026 09:15:23","alice","10.1.2.15",'
        '"https://www.example.com/path","Allowed","GET","200",'
        '"Search Engines","None","5","512","1024","Mozilla/5.0","None"'
    )
    events = parse_nss_feed(f"{header}\n{row}".encode())
    assert len(events) == 1
    assert events[0].action == "Allow"
    assert events[0].client_ip == "10.1.2.15"
    assert events[0].host == "www.example.com"


def test_tsv_default_feed_parses() -> None:
    # Same fields as the CSV fixture, tab-separated and unquoted.
    cells = [
        "Mon Jun 20 15:29:11 2022",
        "new-gre",
        "HTTP",
        "ebay.com/",
        "Blocked",
        "Ebay",
        "Consumer Apps",
        "72",
        "14061",
        "0",
        "0",
        "Productivity Loss",
        "Shopping and Auctions",
        "Online Shopping",
        "None",
        "None",
        "0",
        "None",
        "None",
        "new-gre",
        "Default Department",
        "172.17.3.49",
        "66.211.175.229",
        "GET",
        "403",
        "curl/7.68.0",
        "None",
        "FwFilter",
        "Firewall_1",
        "Other",
        "None",
        "NA",
        "NA",
        "N/A",
    ]
    events = parse_nss_feed("\t".join(cells).encode())
    assert len(events) == 1
    assert events[0].action == "Block"
    assert events[0].client_ip == "172.17.3.49"
    assert events[0].host == "ebay.com"


def test_allowed_normalizes_to_allow() -> None:
    record = {
        "time": "Thu Sep 10 2026 09:15:23",
        "cip": "10.0.0.1",
        "eurl": "https://example.com/",
        "action": "Allowed",
        "reqmethod": "GET",
        "respcode": "200",
        "riskscore": "0",
        "reqsize": "0",
        "respsize": "0",
    }
    events = parse_nss_feed(json.dumps([record]).encode())
    assert events[0].action == "Allow"


def test_iso_timestamp_accepted() -> None:
    record = {
        "time": "2026-09-10T09:15:23Z",
        "cip": "10.0.0.1",
        "eurl": "https://example.com/",
        "action": "Allow",
    }
    events = parse_nss_feed(json.dumps([record]).encode())
    assert events[0].timestamp == datetime(2026, 9, 10, 9, 15, 23, tzinfo=UTC)


def test_wrong_column_count_row_is_skipped() -> None:
    good = CSV_FIXTURE.read_text().strip()
    payload = f'{good}\n"Mon Jun 20 15:29:11 2022","too-short"\n'.encode()
    events = parse_nss_feed(payload)
    assert len(events) == 1
    assert events[0].client_ip == "172.17.3.49"
