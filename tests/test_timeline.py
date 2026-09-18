"""Tests for app.service.timeline (pure - no DB, no HTTP).

Uses the shared fixture for the happy path, plus synthetic lists for the
edge cases: empty events, a single shared timestamp, and aggregate anomalies
with no timestamp.
"""

from datetime import UTC, datetime

from app.model.event import EventOut
from app.model.summary import AnomalyOut
from app.service.parsing import parse_nss_feed
from app.service.timeline import build_summary
from tests.test_parsing import FIXTURE


def _events() -> list[EventOut]:
    parsed = parse_nss_feed(FIXTURE.read_bytes())
    return [
        EventOut(id=index + 1, **event.model_dump(exclude={"raw"}))
        for index, event in enumerate(parsed)
    ]


def _anomaly(timestamp: datetime | None) -> AnomalyOut:
    return AnomalyOut(
        id=1,
        rule="threat-detected",
        severity="high",
        title="Malware blocked",
        description="desc",
        event_id=1 if timestamp is not None else None,
        timestamp=timestamp,
    )


def test_summary_headline_stats() -> None:
    events = _events()
    summary = build_summary(42, events, [])
    assert summary.upload_id == 42
    assert summary.total_events == 6
    assert summary.unique_clients == 6
    assert summary.unique_users == 5
    assert summary.blocked_count == 2
    assert summary.allowed_count == 4
    assert summary.time_range_start == min(event.timestamp for event in events)
    assert summary.time_range_end == max(event.timestamp for event in events)


def test_timeline_buckets_are_aligned_and_sorted() -> None:
    summary = build_summary(42, _events(), [])
    # 03:12 → 13:05 spans 15-minute buckets from 03:00 through 13:00 (41 slots).
    assert len(summary.timeline) == 41
    assert sum(bucket.event_count for bucket in summary.timeline) == 6
    assert sum(bucket.blocked_count for bucket in summary.timeline) == 2
    starts = [bucket.bucket_start for bucket in summary.timeline]
    assert starts == sorted(starts)
    assert starts == [
        starts[0] + (starts[1] - starts[0]) * i for i in range(len(starts))
    ]
    for start in starts:
        assert start.tzinfo is not None
        assert start.second == 0
        assert start.minute % 15 == 0
    occupied = [b for b in summary.timeline if b.event_count]
    assert len(occupied) == 6


def test_anomaly_count_is_attached_to_its_bucket() -> None:
    events = _events()
    summary = build_summary(42, events, [_anomaly(events[0].timestamp)])
    assert sum(bucket.anomaly_count for bucket in summary.timeline) == 1


def test_aggregate_anomaly_without_timestamp_is_not_bucketed() -> None:
    events = _events()
    summary = build_summary(42, events, [_anomaly(None)])
    assert sum(bucket.anomaly_count for bucket in summary.timeline) == 0
    assert len(summary.anomalies) == 1


def test_empty_event_list_returns_zeroed_summary() -> None:
    summary = build_summary(7, [], [])
    assert summary.total_events == 0
    assert summary.timeline == []
    assert summary.top_categories == []
    assert summary.top_hosts == []
    assert summary.time_range_start == summary.time_range_end


def test_all_events_share_one_timestamp() -> None:
    moment = datetime(2026, 9, 10, 12, 0, 0, tzinfo=UTC)
    events = [
        EventOut(
            id=index + 1,
            timestamp=moment,
            client_ip=f"10.0.0.{index + 1}",
            url="https://example.com/",
            action="Allow",
        )
        for index in range(3)
    ]
    summary = build_summary(1, events, [])
    assert len(summary.timeline) == 1
    assert summary.timeline[0].event_count == 3
    assert summary.timeline[0].bucket_start == moment


def test_top_lists_exclude_none_and_rank_by_count() -> None:
    summary = build_summary(42, _events(), [])
    assert summary.top_categories[0].category == "Miscellaneous"
    assert summary.top_categories[0].count == 2
    assert all(item.host for item in summary.top_hosts)
