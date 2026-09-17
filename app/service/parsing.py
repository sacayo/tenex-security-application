"""Log parsing pipeline: raw NSS web-log bytes -> list[CanonicalEvent].

Input format: Zscaler "NSS Feed Output Format: Web Logs" with the JSON feed
output type. A file is EITHER a JSON array of record objects OR newline-
delimited JSON (one record per line) - support both. Field mapping and all
format gotchas (hex-escaped URLs, "None" sentinels, timestamp formats) are
documented in spec.md - "Log Format & Canonical Schema".

Test with: uv run pytest tests/test_parsing.py
(sample file: tests/fixtures/sample_nss_web.json)
"""

from app.model.event import CanonicalEvent


def parse_nss_feed(raw: bytes) -> list[CanonicalEvent]:
    """Parse a whole uploaded file into normalized canonical events.

    TODO(spec.md - "Parsing Pipeline"):
      1. Decode bytes -> str (utf-8, errors="replace").
      2. Detect the shape: try json.loads on the whole text (JSON array);
         fall back to parsing non-empty lines one by one (NDJSON).
      3. Map each raw record dict onto CanonicalEvent fields (see the mapping
         table in spec.md). Treat the string "None" as a missing value.
      4. Un-escape hex sequences (%20 -> space) in URL/host/referrer fields.
      5. Parse timestamps to timezone-aware UTC datetimes.
      6. Skip (and count) malformed records rather than crashing the upload.

    Raise ValueError with a clear message when the file is not recognizable
    as NSS web-log JSON at all - the route turns that into a 422.
    """
    raise NotImplementedError("TODO: implement parse_nss_feed (see spec.md)")
