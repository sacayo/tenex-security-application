"""Canonical event schema: the normalized shape every parsed log line becomes.

`app.service.parsing` converts each raw Zscaler NSS web-log record into one
`CanonicalEvent`. Detection rules and the timeline only ever see this shape,
never raw NSS fields. The full NSS field -> canonical field mapping table
lives in spec.md - "Log Format & Canonical Schema".
"""

from pydantic import BaseModel


class CanonicalEvent(BaseModel):
    """One normalized web-log event.

    TODO(spec.md - "Canonical Schema"): declare the fields. Suggested core set
    (canonical name <- NSS JSON field):

        timestamp: datetime      # "time"  (parse to UTC!)
        client_ip: str           # "cip"
        username: str | None     # "login" ("None" means unauthenticated)
        method: str | None       # "reqmethod"
        url: str                 # "eurl"  (hex-unescaped, e.g. %20 -> space)
        host: str | None         # "ehost"
        status_code: int | None  # "respcode"
        action: str              # "action" ("Allow" / "Block")
        url_category: str | None # "urlcat"
        threat_name: str | None  # "threatname" ("None" means clean)
        risk_score: int          # "riskscore" (0-100)
        bytes_sent: int          # "reqsize"
        bytes_received: int      # "respsize"
        user_agent: str | None   # "ua"
        dlp_dictionary: str | None  # "dlpdict" (DLP rule needs it)

    Every other NSS field (sip, dept, location, appname, ...) stays available
    in the events.raw JSONB column - add a canonical field only when a rule
    or the UI actually needs it.

    Tip: default every optional field to None so partial records still parse.
    """


class EventOut(BaseModel):
    """The event shape the API returns (CanonicalEvent + its database id).

    TODO: same fields as CanonicalEvent plus `id: int`.
    """


class EventPage(BaseModel):
    """One page of events for GET /api/uploads/{id}/events.

    TODO: fields - items: list[EventOut], total: int, limit: int, offset: int.
    """
