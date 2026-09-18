"""Narrative building blocks: everything about the LLM brief that is *pure*.

This module never does I/O. It turns a `SummaryResponse` into the compact
facts block the model is shown, owns the prompt text, computes the risk
level deterministically, and validates what comes back - including a
grounding check that rejects any IP or hostname the model was not told
about. The HTTP call itself lives in `app.llm.client`; orchestration in
`app.llm.generate`.

Why a facts block and not the raw logs: the model only ever sees numbers
and rule output that the deterministic layer already produced. That caps
tokens, keeps raw URLs/user agents off the wire, and makes grounding
checkable - if a host is not in `facts`, the model made it up.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from app.model.narrative import NarrativeSections, RiskLevel
from app.model.summary import AnomalyOut, SummaryResponse

# Bump whenever SYSTEM_PROMPT / build_facts / JSON_SCHEMA change in a way that
# should invalidate cached narratives. Stored alongside each row.
PROMPT_VERSION = "2026-09-18.2"

MAX_FACT_ANOMALIES = 15
MAX_DESCRIPTION_CHARS = 300

_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)

# Strip full URLs and bare www hosts from anomaly text before it reaches the
# model. Hosts already listed in top_hosts stay via that line; IPs stay.
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
# Detection descriptions use "{username} ({ip})" — replace the login token.
_ACTOR_IP_RE = re.compile(
    r"\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|"
    r"[A-Za-z][A-Za-z0-9._-]{1,63})\s+(\(\d{1,3}(?:\.\d{1,3}){3}\))"
)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

SYSTEM_PROMPT = """You are a security analyst writing a short brief for a non-specialist reader (an IT manager, not a SOC engineer) about one batch of Zscaler web-proxy logs.

You will be given a FACTS block. It contains every number and every finding that a deterministic rules engine already computed. Your job is to explain it, not to analyse the logs yourself.

Rules:
- Use ONLY the facts provided. Do not invent hosts, IP addresses, usernames, counts, times, or threats that are not in the FACTS block.
- Do not speculate about attacker intent or root cause beyond what the findings state. Prefer "the logs show" over "the attacker".
- Plain language. Expand jargon on first use (e.g. "DLP (data loss prevention)").
- If there are no anomalies, say so plainly and keep recommendations proportionate (routine monitoring, no dramatic action).
- Never quote or reproduce URLs.

Write:
- headline: one sentence, at most 15 words, stating the overall picture.
- overview: 2 to 4 sentences summarising volume, time span, and the most important finding.
- key_findings: 2 to 5 short bullets, most severe first, each grounded in a specific fact.
- recommended_actions: 2 to 5 short, concrete next steps proportionate to the risk level.

Respond with a single JSON object matching the schema you were given and nothing else."""

# Hand-written (rather than derived from the Pydantic model) so the grammar
# handed to vLLM stays small and only uses widely supported keywords.
JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "overview": {"type": "string"},
        "key_findings": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 6,
        },
        "recommended_actions": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 6,
        },
    },
    "required": ["headline", "overview", "key_findings", "recommended_actions"],
    "additionalProperties": False,
}


class NarrativeValidationError(ValueError):
    """The model's output was well-formed JSON but failed our checks."""


# --------------------------------------------------------------------------
# Risk level
# --------------------------------------------------------------------------


def risk_level(anomalies: Iterable[AnomalyOut]) -> RiskLevel:
    """Highest severity present, or "none". Never delegated to the model."""
    severities = {anomaly.severity for anomaly in anomalies}
    if "high" in severities:
        return "high"
    if "medium" in severities:
        return "medium"
    if "low" in severities:
        return "low"
    return "none"


# --------------------------------------------------------------------------
# Facts block
# --------------------------------------------------------------------------


def _fmt_time(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S UTC")


def _fmt_duration(start: datetime, end: datetime) -> str:
    total = int((end - start).total_seconds())
    if total < 60:
        return f"{total}s"
    hours, remainder = divmod(total, 3600)
    minutes = remainder // 60
    if hours == 0:
        return f"{minutes}m"
    if hours < 48:
        return f"{hours}h {minutes:02d}m"
    return f"{hours // 24}d {hours % 24}h"


def _truncate(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _sanitize_for_facts(text: str) -> str:
    """Remove URLs and login identifiers before text enters the facts block.

    Keeps client IPs (and the ``(ip)`` paren form from detection) so grounding
    still works. Detection descriptions for the UI are left untouched.
    """
    cleaned = _URL_RE.sub("[url]", text)
    cleaned = _ACTOR_IP_RE.sub(r"user \2", cleaned)
    cleaned = _EMAIL_RE.sub("user", cleaned)
    return cleaned


def build_facts(summary: SummaryResponse) -> str:
    """Deterministic, compact facts block. Same summary -> same string."""
    lines: list[str] = []
    lines.append(
        "FACTS (pre-computed by deterministic rules; the only source of truth)"
    )
    lines.append(
        f"Time range: {_fmt_time(summary.time_range_start)} to "
        f"{_fmt_time(summary.time_range_end)} "
        f"(span {_fmt_duration(summary.time_range_start, summary.time_range_end)})"
    )
    lines.append(
        f"Total events: {summary.total_events} | "
        f"Unique client IPs: {summary.unique_clients} | "
        f"Unique users: {summary.unique_users}"
    )
    lines.append(
        f"Blocked by policy: {summary.blocked_count} | Allowed: {summary.allowed_count}"
    )

    if summary.top_categories:
        cats = ", ".join(f"{c.category} ({c.count})" for c in summary.top_categories)
        lines.append(f"Top URL categories: {cats}")
    if summary.top_hosts:
        hosts = ", ".join(f"{h.host} ({h.count})" for h in summary.top_hosts)
        lines.append(f"Top hosts: {hosts}")

    level = risk_level(summary.anomalies)
    lines.append(f"Overall risk level (computed): {level}")

    anomalies = sorted(
        summary.anomalies,
        key=lambda a: (_SEVERITY_RANK.get(a.severity, 9), a.timestamp or _EPOCH),
    )
    total = len(anomalies)
    shown = anomalies[:MAX_FACT_ANOMALIES]
    if total == 0:
        lines.append("Anomalies: none detected by any rule.")
    else:
        lines.append(f"Anomalies: {total} total, {len(shown)} listed by severity:")
        for anomaly in shown:
            when = f" at {_fmt_time(anomaly.timestamp)}" if anomaly.timestamp else ""
            title = _sanitize_for_facts(anomaly.title)
            description = _sanitize_for_facts(anomaly.description)
            lines.append(
                f"- [{anomaly.severity}] {_truncate(title, MAX_DESCRIPTION_CHARS)}"
                f"{when}: {_truncate(description, MAX_DESCRIPTION_CHARS)}"
            )
        if total > len(shown):
            lines.append(
                f"...and {total - len(shown)} more lower-severity anomalies not listed."
            )

    return "\n".join(lines)


# --------------------------------------------------------------------------
# Output handling
# --------------------------------------------------------------------------

_THINK_BLOCK = re.compile(r"^\s*<think>.*?</think>\s*", re.DOTALL)
_THINK_OPEN = re.compile(r"^\s*<think>\s*")


def strip_thinking(text: str) -> str:
    """Drop a leading `<think>...</think>` block if the server leaked one.

    Thinking is disabled per-request, so this is normally a no-op. Kept as a
    cheap guard against a misconfigured server (no reasoning parser).
    """
    stripped, count = _THINK_BLOCK.subn("", text, count=1)
    if count:
        return stripped
    return _THINK_OPEN.sub("", text, count=1)


def empty_narrative() -> NarrativeSections:
    """Canned brief for an upload with zero events (no model call needed)."""
    return NarrativeSections(
        headline="No web-log events were found in this upload.",
        overview=(
            "The file parsed successfully but contained no web-proxy events, "
            "so there is nothing to assess. No anomaly rules were evaluated."
        ),
        key_findings=["Zero events parsed; no traffic to analyse."],
        recommended_actions=[
            "Confirm the export covers the intended time window and log type.",
            "Re-export from Zscaler NSS and upload again.",
        ],
    )


_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
# label(.label)+.tld where the TLD is 2+ letters - avoids "e.g." / "1.5".
_HOSTNAME = re.compile(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b", re.IGNORECASE)


def _entities(text: str) -> set[str]:
    found = {m.group(0) for m in _IPV4.finditer(text)}
    found |= {m.group(0).lower() for m in _HOSTNAME.finditer(text)}
    return found


def _joined(sections: NarrativeSections) -> str:
    return "\n".join(
        [
            sections.headline,
            sections.overview,
            *sections.key_findings,
            *sections.recommended_actions,
        ]
    )


def validate_sections(raw: dict[str, Any], facts: str) -> NarrativeSections:
    """Shape, length, and grounding checks. Raises NarrativeValidationError."""
    try:
        sections = NarrativeSections.model_validate(raw)
    except ValidationError as exc:
        raise NarrativeValidationError(
            f"schema mismatch: {exc.errors()[0]['msg']}"
        ) from exc

    if not sections.headline.strip():
        raise NarrativeValidationError("empty headline")
    if not sections.overview.strip():
        raise NarrativeValidationError("empty overview")
    if not sections.key_findings or not all(s.strip() for s in sections.key_findings):
        raise NarrativeValidationError("key_findings missing or blank")
    if not sections.recommended_actions or not all(
        s.strip() for s in sections.recommended_actions
    ):
        raise NarrativeValidationError("recommended_actions missing or blank")

    allowed = _entities(facts)
    mentioned = _entities(_joined(sections))
    unknown = sorted(mentioned - allowed)
    if unknown:
        raise NarrativeValidationError(
            "ungrounded entities not present in facts: " + ", ".join(unknown[:5])
        )

    return sections
