"""Tests for app.service.detection - one test per rule, positive AND negative.

The fixture file tests/fixtures/sample_nss_web.json is designed to trigger
several rules at once:

    record 700003  threatname="Trojan.Win32.FakeAV"  -> threat-detected
    record 700004  riskscore=78, reqsize=25 MB       -> high-risk-score, large-upload
    record 700005  dlpdict="Credit Cards"            -> dlp-violation
    record 700002  urlcat="Gambling", action=Block   -> suspicious-url-category
    record 700006  03:12, login="None"               -> off-hours

Suggested cases (see spec.md - "Testing Strategy"):
    - each rule fires on the fixture record(s) above
    - each rule does NOT fire on a clean event (negative test)
    - aggregate rules (burst, repeated blocks, beaconing) only fire past
      their thresholds - test just under and just over the boundary
    - anomalies carry the right severity and a human-readable title

Build tiny synthetic CanonicalEvent lists for unit tests; use the fixture
for one end-to-end run_rules test.
"""

import pytest

from app.service.detection import run_rules
from app.service.parsing import parse_nss_feed
from tests.test_parsing import FIXTURE


@pytest.mark.skip(reason="rules not implemented yet - remove to start TDD")
def test_run_rules_on_fixture_example() -> None:
    events = parse_nss_feed(FIXTURE.read_bytes())
    anomalies = run_rules(events)
    rules_hit = {a.rule for a in anomalies}
    assert "threat-detected" in rules_hit
    assert "dlp-violation" in rules_hit
