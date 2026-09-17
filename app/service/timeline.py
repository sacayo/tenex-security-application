"""Timeline + summary building.

Turns stored events and anomalies into the SummaryResponse the frontend
renders: headline stats, top-N lists, and fixed-width time buckets for the
timeline chart.

Bucketing guidance (spec.md - "API Contract"): pick a bucket width that
keeps the chart readable - e.g. divide the observed time range into at most
60 buckets, rounding to a "nice" width (1m / 5m / 15m / 1h / 1d...).
"""

from app.model.event import EventOut
from app.model.summary import AnomalyOut, SummaryResponse


def build_summary(
    upload_id: int,
    events: list[EventOut],
    anomalies: list[AnomalyOut],
) -> SummaryResponse:
    """Aggregate events + anomalies into the summary response.

    TODO(spec.md - "API Contract" -> GET /api/uploads/{id}/summary):
      1. Compute time_range_start/end from min/max event timestamps.
      2. Compute total/unique/blocked/allowed counts.
      3. Compute top_categories and top_hosts (top 5-10 by count).
      4. Bucket events into TimelineBucket rows (see module docstring).
         Attach each bucket's anomaly_count by matching anomaly timestamps.
      5. Assemble and return the SummaryResponse.

    Edge cases to handle: empty event list (return zeroed summary), and all
    events sharing one timestamp (a single bucket is fine).
    """
    raise NotImplementedError("TODO: implement build_summary (see spec.md)")
