"""Tests for app.service.parsing - write these as you build the parser.

Suggested cases (see spec.md - "Testing Strategy"):

  happy path
    - JSON array file (tests/fixtures/sample_nss_web.json) -> 6 events
    - NDJSON variant (one record per line) -> same result
    - fields map correctly: cip->client_ip, login->username, respcode->int,
      riskscore->int, reqsize/respsize->int
    - timestamps become timezone-aware UTC datetimes
    - "%20" in eurl is decoded to a space

  sentinel handling
    - "None" strings (login, threatname, dlpdict, ua) become None

  robustness
    - a malformed line is skipped, not fatal; valid lines still parse
    - completely unrecognizable content raises ValueError (route -> 422)
    - empty file raises ValueError (route -> 400)

The example below shows the pattern: load the fixture, call the function,
assert on CanonicalEvent fields. Remove the skip marker once you start.
"""

import json
from pathlib import Path

import pytest

from app.service.parsing import parse_nss_feed

FIXTURE = Path(__file__).parent / "fixtures" / "sample_nss_web.json"


@pytest.mark.skip(reason="parser not implemented yet - remove to start TDD")
def test_parse_fixture_example() -> None:
    events = parse_nss_feed(FIXTURE.read_bytes())
    raw = json.loads(FIXTURE.read_text())
    assert len(events) == len(raw)
    assert events[0].client_ip == "10.1.2.15"
