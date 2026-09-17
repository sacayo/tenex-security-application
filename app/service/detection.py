"""Rule-based anomaly detection.

Pure functions over parsed events: no database, no FastAPI. Each rule is a
small function that looks at the whole event list and yields DetectedAnomaly
objects; `run_rules` simply runs every rule and concatenates the results.

The full rule catalog (thresholds, severities, rationale) is in
spec.md - "Detection Rules". Start with the stateless rules (they look at
one event at a time) before the aggregate ones (bursts, beaconing).

Test with: uv run pytest tests/test_detection.py
"""

from app.model.event import CanonicalEvent
from app.model.summary import DetectedAnomaly


def run_rules(events: list[CanonicalEvent]) -> list[DetectedAnomaly]:
    """Run every detection rule over the parsed events.

    TODO(spec.md - "Detection Rules"): implement the rules as small
    functions below and call them all here. Suggested signatures:

        def rule_threat_detected(events) -> Iterable[DetectedAnomaly]:
            # threat_name present -> one anomaly per event (severity: high)

        def rule_high_risk_score(events, threshold: int = 75):
            # risk_score >= threshold -> medium

        def rule_suspicious_url_category(events):
            # url_category in a blocklist set -> medium

        def rule_dlp_violation(events):
            # dlp dictionary hit -> high

        def rule_blocked_repeated(events, threshold: int = 10):
            # same client_ip blocked > threshold times -> medium (aggregate:
            # one anomaly per offender, event_index=None)

        def rule_request_burst(events, window_seconds: int = 60, threshold: int = 100):
            # one client_ip with > threshold events inside any window -> medium

        def rule_large_upload(events, bytes_threshold: int = 10_000_000):
            # bytes_sent above threshold -> high (possible exfiltration)

        def rule_off_hours(events, start_hour: int = 19, end_hour: int = 7):
            # event outside 07:00-19:00 local -> low

    Return the concatenation of all rule outputs.
    """
    raise NotImplementedError("TODO: implement detection rules (see spec.md)")
