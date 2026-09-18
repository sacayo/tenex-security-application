"""Repository round-trip tests against the throwaway `anomaly_test` database.

Covers status transitions, insert/read-back, the critical `event_index` ->
`events.id` mapping, filters/pagination, ordering, and FK cascade.
"""

from datetime import UTC, datetime

from sqlalchemy import func, select

from app.data import repository
from app.data.tables import Anomaly, Event
from app.model.event import CanonicalEvent
from app.model.summary import DetectedAnomaly


def _canonical(**overrides) -> CanonicalEvent:
    base = {
        "timestamp": datetime(2026, 9, 10, 12, 0, 0, tzinfo=UTC),
        "client_ip": "10.0.0.1",
        "url": "https://example.com/",
        "action": "Allow",
        "risk_score": 0,
        "raw": {"recordid": "1"},
    }
    base.update(overrides)
    return CanonicalEvent(**base)


def _anomaly(**overrides) -> DetectedAnomaly:
    base = {
        "rule": "threat-detected",
        "severity": "high",
        "title": "Malware blocked",
        "description": "desc",
        "event_index": None,
    }
    base.update(overrides)
    return DetectedAnomaly(**base)


def test_create_upload_starts_in_parsing(session) -> None:
    upload = repository.create_upload(session, filename="nss.json", file_size=123)
    assert upload.id is not None
    assert upload.status == "parsing"
    assert upload.file_size_bytes == 123


def test_mark_upload_completed(session) -> None:
    upload = repository.create_upload(session, filename="nss.json", file_size=1)
    repository.mark_upload_completed(session, upload.id, 6, 7)
    refreshed = repository.get_upload(session, upload.id)
    assert refreshed is not None
    assert refreshed.status == "completed"
    assert refreshed.event_count == 6
    assert refreshed.anomaly_count == 7
    assert refreshed.processed_at is not None


def test_mark_upload_failed(session) -> None:
    upload = repository.create_upload(session, filename="nss.json", file_size=1)
    repository.mark_upload_failed(session, upload.id, "bad json")
    refreshed = repository.get_upload(session, upload.id)
    assert refreshed is not None
    assert refreshed.status == "failed"
    assert refreshed.error_message == "bad json"


def test_insert_events_preserves_raw_and_order(session) -> None:
    upload = repository.create_upload(session, filename="nss.json", file_size=1)
    rows = repository.insert_events(
        session,
        upload.id,
        [_canonical(), _canonical(client_ip="10.0.0.2")],
    )
    assert rows[0].raw == {"recordid": "1"}
    assert rows[1].client_ip == "10.0.0.2"
    assert rows[0].id < rows[1].id


def test_insert_anomalies_maps_event_index_to_event_id(session) -> None:
    upload = repository.create_upload(session, filename="nss.json", file_size=1)
    rows = repository.insert_events(
        session,
        upload.id,
        [_canonical(), _canonical(client_ip="10.0.0.2")],
    )
    event_ids = [row.id for row in rows]
    repository.insert_anomalies(
        session,
        upload.id,
        [
            _anomaly(event_index=1),
            _anomaly(rule="repeated-blocks", event_index=None),
        ],
        event_ids,
    )
    anomalies = repository.get_anomalies(session, upload.id)
    assert anomalies[0].event_id == event_ids[1]
    assert anomalies[1].event_id is None


def test_get_upload_unknown_returns_none(session) -> None:
    assert repository.get_upload(session, 999999) is None


def test_list_events_pagination_and_filters(session) -> None:
    upload = repository.create_upload(session, filename="nss.json", file_size=1)
    repository.insert_events(
        session,
        upload.id,
        [
            _canonical(client_ip="10.0.0.1", action="Allow"),
            _canonical(client_ip="10.0.0.2", action="Block", url_category="Gambling"),
            _canonical(client_ip="10.0.0.3", action="Block", url_category="Gambling"),
        ],
    )

    page, total = repository.list_events(session, upload.id, limit=2, offset=0)
    assert total == 3
    assert len(page) == 2

    blocked, blocked_total = repository.list_events(
        session, upload.id, limit=50, offset=0, action="Block"
    )
    assert blocked_total == 2
    assert all(event.action == "Block" for event in blocked)

    _, gambling_total = repository.list_events(
        session, upload.id, limit=50, offset=0, url_category="Gambling"
    )
    assert gambling_total == 2


def test_list_events_anomalies_only(session) -> None:
    upload = repository.create_upload(session, filename="nss.json", file_size=1)
    rows = repository.insert_events(
        session, upload.id, [_canonical(), _canonical(client_ip="10.0.0.2")]
    )
    event_ids = [row.id for row in rows]
    repository.insert_anomalies(
        session, upload.id, [_anomaly(event_index=1)], event_ids
    )

    items, total = repository.list_events(
        session, upload.id, limit=50, offset=0, anomalies_only=True
    )
    assert total == 1
    assert items[0].id == event_ids[1]


def test_get_events_for_summary_is_time_ordered(session) -> None:
    upload = repository.create_upload(session, filename="nss.json", file_size=1)
    repository.insert_events(
        session,
        upload.id,
        [
            _canonical(timestamp=datetime(2026, 9, 10, 13, 0, tzinfo=UTC)),
            _canonical(timestamp=datetime(2026, 9, 10, 11, 0, tzinfo=UTC)),
        ],
    )
    events = repository.get_events_for_summary(session, upload.id)
    stamps = [event.timestamp for event in events]
    assert stamps == sorted(stamps)


def test_deleting_upload_cascades_to_children(session) -> None:
    upload = repository.create_upload(session, filename="nss.json", file_size=1)
    rows = repository.insert_events(session, upload.id, [_canonical()])
    repository.insert_anomalies(
        session, upload.id, [_anomaly(event_index=0)], [rows[0].id]
    )

    session.delete(upload)
    session.commit()

    assert session.scalar(select(func.count()).select_from(Event)) == 0
    assert session.scalar(select(func.count()).select_from(Anomaly)) == 0
