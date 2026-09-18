"""Timeline + summary building.

Turns stored events and anomalies into the SummaryResponse the frontend
renders: headline stats, top-N lists, and fixed-width time buckets for the
timeline chart.

Bucketing (spec.md - "API Contract"): pick the smallest "nice" width
(1m / 5m / 15m / 1h / 6h / 1d) that keeps the observed range within 60
buckets. Buckets are aligned to the epoch so their starts are stable.
"""

import logging
from collections import Counter
from datetime import UTC, datetime, timedelta

from app.model.event import EventOut
from app.model.summary import (
    AnomalyOut,
    CategoryCount,
    HostCount,
    SummaryResponse,
    TimelineBucket,
)

logger = logging.getLogger(__name__)

BUCKET_WIDTHS_SECONDS = (60, 300, 900, 3600, 21600, 86400)
MAX_BUCKETS = 60
TOP_N = 5
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _select_width(span_seconds: float) -> int:
    for width in BUCKET_WIDTHS_SECONDS:
        if span_seconds <= width * MAX_BUCKETS:
            return width
    return BUCKET_WIDTHS_SECONDS[-1]


def _bucket_start(timestamp: datetime, width: int) -> datetime:
    seconds = int(timestamp.timestamp())
    return _EPOCH + timedelta(seconds=(seconds // width) * width)


def build_summary(
    upload_id: int,
    events: list[EventOut],
    anomalies: list[AnomalyOut],
) -> SummaryResponse:
    """Aggregate events + anomalies into the summary response."""
    if not events:
        now = datetime.now(UTC)
        logger.warning("summary for upload_id=%s has no events", upload_id)
        return SummaryResponse(
            upload_id=upload_id,
            time_range_start=now,
            time_range_end=now,
            total_events=0,
            unique_clients=0,
            unique_users=0,
            blocked_count=0,
            allowed_count=0,
            top_categories=[],
            top_hosts=[],
            timeline=[],
            anomalies=anomalies,
        )

    timestamps = [event.timestamp for event in events]
    time_range_start = min(timestamps)
    time_range_end = max(timestamps)
    width = _select_width((time_range_end - time_range_start).total_seconds())

    buckets: dict[datetime, dict[str, int]] = {}
    for event in events:
        key = _bucket_start(event.timestamp, width)
        bucket = buckets.setdefault(
            key, {"event_count": 0, "blocked_count": 0, "anomaly_count": 0}
        )
        bucket["event_count"] += 1
        if event.action == "Block":
            bucket["blocked_count"] += 1

    for anomaly in anomalies:
        if anomaly.timestamp is None:
            continue
        key = _bucket_start(anomaly.timestamp, width)
        if key in buckets:
            buckets[key]["anomaly_count"] += 1

    timeline = [
        TimelineBucket(bucket_start=key, **counts)
        for key, counts in sorted(buckets.items())
    ]

    categories = Counter(
        event.url_category for event in events if event.url_category is not None
    )
    hosts = Counter(event.host for event in events if event.host is not None)

    logger.debug(
        "summary upload_id=%s events=%d buckets=%d width=%ds",
        upload_id,
        len(events),
        len(timeline),
        width,
    )

    return SummaryResponse(
        upload_id=upload_id,
        time_range_start=time_range_start,
        time_range_end=time_range_end,
        total_events=len(events),
        unique_clients=len({event.client_ip for event in events}),
        unique_users=len({event.username for event in events if event.username}),
        blocked_count=sum(1 for event in events if event.action == "Block"),
        allowed_count=sum(1 for event in events if event.action == "Allow"),
        top_categories=[
            CategoryCount(category=category, count=count)
            for category, count in categories.most_common(TOP_N)
        ],
        top_hosts=[
            HostCount(host=host, count=count)
            for host, count in hosts.most_common(TOP_N)
        ],
        timeline=timeline,
        anomalies=anomalies,
    )
