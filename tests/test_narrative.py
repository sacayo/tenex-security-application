"""Unit tests for app/service/narrative.py (pure - no I/O, no model)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.model.summary import (
    AnomalyOut,
    CategoryCount,
    HostCount,
    SummaryResponse,
)
from app.service.narrative import (
    JSON_SCHEMA,
    MAX_FACT_ANOMALIES,
    NarrativeValidationError,
    build_facts,
    empty_narrative,
    risk_level,
    strip_thinking,
    validate_sections,
)

T0 = datetime(2022, 6, 20, 15, 0, tzinfo=UTC)


def _anomaly(i: int, severity: str, description: str = "detail") -> AnomalyOut:
    return AnomalyOut(
        id=i,
        rule="rule-x",
        severity=severity,  # type: ignore[arg-type]
        title=f"Anomaly {i}",
        description=description,
        event_id=i,
        timestamp=T0 + timedelta(minutes=i),
    )


def _summary(anomalies: list[AnomalyOut] | None = None) -> SummaryResponse:
    return SummaryResponse(
        upload_id=1,
        time_range_start=T0,
        time_range_end=T0 + timedelta(hours=1, minutes=5),
        total_events=42,
        unique_clients=3,
        unique_users=2,
        blocked_count=5,
        allowed_count=37,
        top_categories=[CategoryCount(category="Online Shopping", count=10)],
        top_hosts=[HostCount(host="ebay.com", count=10)],
        timeline=[],
        anomalies=anomalies or [],
    )


# --- risk_level -------------------------------------------------------------


def test_risk_level_none_when_no_anomalies() -> None:
    assert risk_level([]) == "none"


def test_risk_level_takes_highest_severity() -> None:
    assert risk_level([_anomaly(1, "low"), _anomaly(2, "medium")]) == "medium"
    assert (
        risk_level([_anomaly(1, "low"), _anomaly(2, "high"), _anomaly(3, "medium")])
        == "high"
    )
    assert risk_level([_anomaly(1, "low")]) == "low"


# --- build_facts ------------------------------------------------------------


def test_build_facts_is_deterministic_and_contains_core_numbers() -> None:
    summary = _summary([_anomaly(1, "high", "client 10.0.0.5 hit bad.example.com")])
    facts = build_facts(summary)
    assert facts == build_facts(summary)
    assert "Total events: 42" in facts
    assert "Blocked by policy: 5 | Allowed: 37" in facts
    assert "ebay.com (10)" in facts
    assert "Overall risk level (computed): high" in facts
    assert "[high] Anomaly 1" in facts
    assert "10.0.0.5" in facts


def test_build_facts_orders_by_severity_and_caps_count() -> None:
    anomalies = [_anomaly(i, "low") for i in range(1, MAX_FACT_ANOMALIES + 4)]
    anomalies.append(_anomaly(99, "high"))
    facts = build_facts(_summary(anomalies))
    listed = [line for line in facts.splitlines() if line.startswith("- [")]
    assert len(listed) == MAX_FACT_ANOMALIES
    assert listed[0].startswith("- [high] Anomaly 99")
    assert "...and 4 more lower-severity anomalies not listed." in facts


def test_build_facts_states_no_anomalies_plainly() -> None:
    assert "Anomalies: none detected by any rule." in build_facts(_summary())


def test_build_facts_never_includes_raw_urls_or_usernames() -> None:
    """Descriptions can carry URLs (via host-or-url) and login tokens; facts must not."""
    facts = build_facts(
        _summary(
            [
                _anomaly(
                    1,
                    "high",
                    description=(
                        "carol.davis (10.1.4.22) reached "
                        "https://evil.example/path?q=1 — detected as malware."
                    ),
                )
            ]
        )
    )
    assert "https://" not in facts
    assert "http://" not in facts
    assert "evil.example/path" not in facts
    assert "carol.davis" not in facts
    assert "10.1.4.22" in facts
    assert "user (10.1.4.22)" in facts


# --- strip_thinking ---------------------------------------------------------


def test_strip_thinking_removes_leading_block() -> None:
    assert strip_thinking('<think>hmm\nmore</think>\n{"a":1}') == '{"a":1}'


def test_strip_thinking_is_noop_without_block() -> None:
    assert strip_thinking('{"a":1}') == '{"a":1}'


def test_strip_thinking_handles_unclosed_tag() -> None:
    assert strip_thinking('<think>{"a":1}') == '{"a":1}'


# --- empty_narrative / schema ----------------------------------------------


def test_empty_narrative_validates_against_own_rules() -> None:
    sections = empty_narrative()
    assert validate_sections(sections.model_dump(), facts="") == sections


def test_json_schema_matches_model_fields() -> None:
    assert set(JSON_SCHEMA["required"]) == {
        "headline",
        "overview",
        "key_findings",
        "recommended_actions",
    }
    assert JSON_SCHEMA["additionalProperties"] is False


# --- validate_sections ------------------------------------------------------

GOOD = {
    "headline": "Seven anomalies flagged in one hour of traffic.",
    "overview": "The logs show 42 events. One high-severity threat was blocked.",
    "key_findings": ["A threat was blocked."],
    "recommended_actions": ["Review the affected client."],
}


def test_validate_sections_accepts_grounded_output() -> None:
    facts = build_facts(_summary([_anomaly(1, "high", "client 10.0.0.5")]))
    out = validate_sections(
        {**GOOD, "key_findings": ["Client 10.0.0.5 was blocked."]}, facts
    )
    assert out.key_findings == ["Client 10.0.0.5 was blocked."]


def test_validate_sections_rejects_unknown_ip() -> None:
    facts = build_facts(_summary([_anomaly(1, "high", "client 10.0.0.5")]))
    with pytest.raises(NarrativeValidationError, match="ungrounded.*192.168.1.1"):
        validate_sections({**GOOD, "overview": "Client 192.168.1.1 did it."}, facts)


def test_validate_sections_rejects_unknown_host() -> None:
    facts = build_facts(_summary())
    with pytest.raises(NarrativeValidationError, match="evil.example.com"):
        validate_sections({**GOOD, "headline": "Traffic to evil.example.com"}, facts)


def test_validate_sections_allows_hosts_from_top_hosts() -> None:
    facts = build_facts(_summary())
    out = validate_sections(
        {**GOOD, "headline": "Most traffic went to ebay.com."}, facts
    )
    assert "ebay.com" in out.headline


def test_validate_sections_ignores_abbreviations_and_decimals() -> None:
    facts = build_facts(_summary())
    out = validate_sections(
        {**GOOD, "overview": "Roughly 1.5 events per minute, e.g. shopping."}, facts
    )
    assert out.overview.startswith("Roughly")


def test_validate_sections_rejects_missing_field() -> None:
    bad = {k: v for k, v in GOOD.items() if k != "overview"}
    with pytest.raises(NarrativeValidationError, match="schema mismatch"):
        validate_sections(bad, facts="")


def test_validate_sections_rejects_blank_lists() -> None:
    with pytest.raises(NarrativeValidationError, match="key_findings"):
        validate_sections({**GOOD, "key_findings": []}, facts="")
    with pytest.raises(NarrativeValidationError, match="recommended_actions"):
        validate_sections({**GOOD, "recommended_actions": ["  "]}, facts="")
