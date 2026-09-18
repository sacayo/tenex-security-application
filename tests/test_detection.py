"""Tests for app.service.detection - one test per rule, positive AND negative,
plus threshold boundaries for the aggregate rules.
"""

from datetime import UTC, datetime, timedelta

from app.model.event import CanonicalEvent
from app.service.detection import (
    LARGE_UPLOAD_BYTES,
    OFF_HOURS_END,
    OFF_HOURS_START,
    rule_blocked_repeated,
    rule_dlp_violation,
    rule_high_risk_score,
    rule_large_upload,
    rule_off_hours,
    rule_request_burst,
    rule_suspicious_url_category,
    rule_threat_detected,
    run_rules,
)
from app.service.parsing import parse_nss_feed
from tests.test_parsing import CSV_FIXTURE, FIXTURE


def _event(**overrides) -> CanonicalEvent:
    base = {
        "timestamp": datetime(2026, 9, 10, 12, 0, 0, tzinfo=UTC),
        "client_ip": "10.0.0.1",
        "url": "https://example.com/",
        "action": "Allow",
        "risk_score": 0,
    }
    base.update(overrides)
    return CanonicalEvent(**base)


def test_run_rules_on_fixture() -> None:
    events = parse_nss_feed(FIXTURE.read_bytes())
    anomalies = run_rules(events)
    rules_hit = {a.rule for a in anomalies}
    assert rules_hit == {
        "threat-detected",
        "high-risk-score",
        "suspicious-url-category",
        "dlp-violation",
        "large-upload",
        "off-hours",
    }
    assert len(anomalies) == 7


def test_clean_event_fires_no_rules() -> None:
    assert run_rules([_event()]) == []


def test_single_blocked_shopping_event_fires_no_rules() -> None:
    """A lone Blocked eBay browse (sample-nss-output-logs.txt) is not anomalous."""
    events = parse_nss_feed(CSV_FIXTURE.read_bytes())
    assert len(events) == 1
    assert events[0].action == "Block"
    assert events[0].url_category == "Online Shopping"
    assert run_rules(events) == []


def test_threat_detected_metadata() -> None:
    hits = rule_threat_detected([_event(threat_name="Trojan.Win32.FakeAV", risk_score=92)])
    assert len(hits) == 1
    assert hits[0].severity == "high"
    assert "Trojan.Win32.FakeAV" in hits[0].title
    assert hits[0].event_index == 0


def test_threat_detected_negative() -> None:
    assert rule_threat_detected([_event(threat_name=None)]) == []


def test_high_risk_score_boundary() -> None:
    assert rule_high_risk_score([_event(risk_score=74)]) == []
    assert len(rule_high_risk_score([_event(risk_score=75)])) == 1


def test_suspicious_url_category() -> None:
    assert len(rule_suspicious_url_category([_event(url_category="Gambling")])) == 1
    assert rule_suspicious_url_category([_event(url_category="Search Engines")]) == []
    assert rule_suspicious_url_category([_event(url_category=None)]) == []


def test_dlp_violation() -> None:
    hits = rule_dlp_violation([_event(dlp_dictionary="Credit Cards")])
    assert len(hits) == 1
    assert hits[0].severity == "high"
    assert rule_dlp_violation([_event(dlp_dictionary=None)]) == []


def test_large_upload_boundary() -> None:
    assert rule_large_upload([_event(bytes_sent=LARGE_UPLOAD_BYTES - 1)]) == []
    assert len(rule_large_upload([_event(bytes_sent=LARGE_UPLOAD_BYTES)])) == 1


def test_off_hours_boundary() -> None:
    first_hour = datetime(2026, 9, 10, OFF_HOURS_END, 0, tzinfo=UTC)
    last_hour = datetime(2026, 9, 10, OFF_HOURS_START - 1, 59, tzinfo=UTC)
    edge_evening = datetime(2026, 9, 10, OFF_HOURS_START, 0, tzinfo=UTC)
    night = datetime(2026, 9, 10, 3, 12, tzinfo=UTC)
    assert rule_off_hours([_event(timestamp=first_hour)]) == []
    assert rule_off_hours([_event(timestamp=last_hour)]) == []
    assert len(rule_off_hours([_event(timestamp=edge_evening)])) == 1
    assert len(rule_off_hours([_event(timestamp=night)])) == 1


def test_event_index_points_at_offending_event() -> None:
    events = [_event(), _event(risk_score=90), _event()]
    hits = rule_high_risk_score(events)
    assert [hit.event_index for hit in hits] == [1]


def test_repeated_blocks_boundary() -> None:
    nine = [_event(client_ip="10.0.0.9", action="Block") for _ in range(9)]
    ten = [_event(client_ip="10.0.0.9", action="Block") for _ in range(10)]
    assert rule_blocked_repeated(nine) == []
    hits = rule_blocked_repeated(ten)
    assert len(hits) == 1
    assert hits[0].event_index is None
    assert "10.0.0.9" in hits[0].title


def test_repeated_blocks_ignores_allowed_requests() -> None:
    events = [_event(client_ip="10.0.0.9", action="Allow") for _ in range(20)]
    assert rule_blocked_repeated(events) == []


def test_request_burst_boundary() -> None:
    start = datetime(2026, 9, 10, 12, 0, 0, tzinfo=UTC)
    at_limit = [
        _event(client_ip="10.0.0.7", timestamp=start + timedelta(milliseconds=500 * i))
        for i in range(100)
    ]
    over_limit = [
        _event(client_ip="10.0.0.7", timestamp=start + timedelta(milliseconds=500 * i))
        for i in range(101)
    ]
    assert rule_request_burst(at_limit) == []
    hits = rule_request_burst(over_limit)
    assert len(hits) == 1
    assert hits[0].event_index is None


def test_request_burst_ignores_spread_out_requests() -> None:
    start = datetime(2026, 9, 10, 12, 0, 0, tzinfo=UTC)
    events = [
        _event(client_ip="10.0.0.7", timestamp=start + timedelta(minutes=i))
        for i in range(120)
    ]
    assert rule_request_burst(events) == []
