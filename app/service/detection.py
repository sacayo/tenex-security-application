"""Rule-based anomaly detection.

Pure functions over parsed events. Each rule takes the event list and returns
``DetectedAnomaly`` objects; ``run_rules`` runs them all. Stateless rules
inspect one event; aggregate rules inspect the whole list and return
``event_index=None``. Catalog and thresholds: ``spec.md`` - "Detection Rules".
"""

import logging
from collections import Counter, defaultdict
from datetime import datetime

from app.model.event import CanonicalEvent
from app.model.summary import DetectedAnomaly

logger = logging.getLogger(__name__)

HIGH_RISK_THRESHOLD = 75
SUSPICIOUS_CATEGORIES = frozenset(
    {
        "Gambling",
        "Anonymizers",
        "Phishing",
        "Adult Content",
        "Hacking",
        "Piracy",
    }
)
LARGE_UPLOAD_BYTES = 10 * 1024 * 1024
OFF_HOURS_START = 19
OFF_HOURS_END = 7
REPEATED_BLOCKS_THRESHOLD = 10
BURST_WINDOW_SECONDS = 60
BURST_THRESHOLD = 100

HIGH = "high"
MEDIUM = "medium"
LOW = "low"


def _actor(event: CanonicalEvent) -> str:
    return event.username or "unauthenticated user"


def _target(event: CanonicalEvent) -> str:
    return event.host or event.url


def rule_threat_detected(events: list[CanonicalEvent]) -> list[DetectedAnomaly]:
    """Flag events that name a threat."""
    hits: list[DetectedAnomaly] = []
    for index, event in enumerate(events):
        if event.threat_name is None:
            continue
        hits.append(
            DetectedAnomaly(
                rule="threat-detected",
                severity=HIGH,
                title=f"Malware blocked: {event.threat_name}",
                description=(
                    f"{_actor(event)} ({event.client_ip}) reached {_target(event)} "
                    f"\u2014 detected as {event.threat_name} (risk {event.risk_score})."
                ),
                event_index=index,
            )
        )
    return hits


def rule_high_risk_score(
    events: list[CanonicalEvent], threshold: int = HIGH_RISK_THRESHOLD
) -> list[DetectedAnomaly]:
    """Flag events at or above the risk-score threshold."""
    hits: list[DetectedAnomaly] = []
    for index, event in enumerate(events):
        if event.risk_score < threshold:
            continue
        hits.append(
            DetectedAnomaly(
                rule="high-risk-score",
                severity=MEDIUM,
                title=f"High-risk destination (score {event.risk_score})",
                description=(
                    f"{_actor(event)} ({event.client_ip}) visited {_target(event)} "
                    f"with risk score {event.risk_score}/100."
                ),
                event_index=index,
            )
        )
    return hits


def rule_suspicious_url_category(
    events: list[CanonicalEvent],
    categories: frozenset[str] = SUSPICIOUS_CATEGORIES,
) -> list[DetectedAnomaly]:
    """Flag events in a configured suspicious URL category."""
    hits: list[DetectedAnomaly] = []
    for index, event in enumerate(events):
        if event.url_category not in categories:
            continue
        hits.append(
            DetectedAnomaly(
                rule="suspicious-url-category",
                severity=MEDIUM,
                title=f"Visit to {event.url_category} site",
                description=(
                    f"{_actor(event)} ({event.client_ip}) accessed {_target(event)} "
                    f"categorized as {event.url_category}."
                ),
                event_index=index,
            )
        )
    return hits


def rule_dlp_violation(events: list[CanonicalEvent]) -> list[DetectedAnomaly]:
    """Flag events that matched a DLP dictionary."""
    hits: list[DetectedAnomaly] = []
    for index, event in enumerate(events):
        if event.dlp_dictionary is None:
            continue
        hits.append(
            DetectedAnomaly(
                rule="dlp-violation",
                severity=HIGH,
                title=f"DLP match: {event.dlp_dictionary}",
                description=(
                    f"{_actor(event)} ({event.client_ip}) triggered DLP dictionary "
                    f"'{event.dlp_dictionary}' on {_target(event)}."
                ),
                event_index=index,
            )
        )
    return hits


def rule_large_upload(
    events: list[CanonicalEvent], bytes_threshold: int = LARGE_UPLOAD_BYTES
) -> list[DetectedAnomaly]:
    """Flag uploads at or above the byte threshold."""
    hits: list[DetectedAnomaly] = []
    for index, event in enumerate(events):
        if event.bytes_sent < bytes_threshold:
            continue
        megabytes = event.bytes_sent / (1024 * 1024)
        hits.append(
            DetectedAnomaly(
                rule="large-upload",
                severity=HIGH,
                title=f"{megabytes:.0f} MB uploaded to {_target(event)}",
                description=(
                    f"{_actor(event)} ({event.client_ip}) uploaded {megabytes:.1f} MB "
                    f"to {_target(event)} (possible exfiltration)."
                ),
                event_index=index,
            )
        )
    return hits


def rule_off_hours(
    events: list[CanonicalEvent],
    start_hour: int = OFF_HOURS_START,
    end_hour: int = OFF_HOURS_END,
) -> list[DetectedAnomaly]:
    """Flag events outside the business-hours window."""
    hits: list[DetectedAnomaly] = []
    for index, event in enumerate(events):
        hour = event.timestamp.hour
        if end_hour <= hour < start_hour:
            continue
        clock = event.timestamp.strftime("%H:%M")
        hits.append(
            DetectedAnomaly(
                rule="off-hours",
                severity=LOW,
                title=f"Activity at {clock}",
                description=(
                    f"{_actor(event)} ({event.client_ip}) was active at {clock} UTC, "
                    f"outside {end_hour:02d}:00-{start_hour:02d}:00."
                ),
                event_index=index,
            )
        )
    return hits


def rule_blocked_repeated(
    events: list[CanonicalEvent], threshold: int = REPEATED_BLOCKS_THRESHOLD
) -> list[DetectedAnomaly]:
    """Flag clients blocked repeatedly (aggregate)."""
    counts = Counter(event.client_ip for event in events if event.action == "Block")
    hits: list[DetectedAnomaly] = []
    for client_ip, count in counts.items():
        if count < threshold:
            continue
        hits.append(
            DetectedAnomaly(
                rule="repeated-blocks",
                severity=MEDIUM,
                title=f"{client_ip} blocked {count} times",
                description=(
                    f"{client_ip} had {count} blocked requests "
                    f"(threshold {threshold}); possible policy evasion."
                ),
                event_index=None,
            )
        )
    return hits


def _max_in_window(timestamps: list[datetime], window_seconds: int) -> int:
    times = sorted(timestamps)
    left = 0
    best = 0
    for right, current in enumerate(times):
        while (current - times[left]).total_seconds() > window_seconds:
            left += 1
        best = max(best, right - left + 1)
    return best


def rule_request_burst(
    events: list[CanonicalEvent],
    window_seconds: int = BURST_WINDOW_SECONDS,
    threshold: int = BURST_THRESHOLD,
) -> list[DetectedAnomaly]:
    """Flag clients exceeding the request-rate threshold (aggregate)."""
    by_client: defaultdict[str, list[datetime]] = defaultdict(list)
    for event in events:
        by_client[event.client_ip].append(event.timestamp)

    hits: list[DetectedAnomaly] = []
    for client_ip, timestamps in by_client.items():
        peak = _max_in_window(timestamps, window_seconds)
        if peak <= threshold:
            continue
        hits.append(
            DetectedAnomaly(
                rule="request-burst",
                severity=MEDIUM,
                title=f"{client_ip}: {peak} requests in {window_seconds}s",
                description=(
                    f"{client_ip} made {peak} requests within {window_seconds}s "
                    f"(threshold {threshold}); possible automated activity."
                ),
                event_index=None,
            )
        )
    return hits


_RULES = (
    rule_threat_detected,
    rule_high_risk_score,
    rule_suspicious_url_category,
    rule_dlp_violation,
    rule_large_upload,
    rule_off_hours,
    rule_blocked_repeated,
    rule_request_burst,
)


def run_rules(events: list[CanonicalEvent]) -> list[DetectedAnomaly]:
    """Run every detection rule and return the concatenated anomalies."""
    anomalies: list[DetectedAnomaly] = []
    for rule in _RULES:
        hits = rule(events)
        if hits:
            logger.debug("rule=%s hits=%d", rule.__name__, len(hits))
        anomalies.extend(hits)
    logger.info(
        "detected %d anomaly(ies) from %d event(s)", len(anomalies), len(events)
    )
    return anomalies
