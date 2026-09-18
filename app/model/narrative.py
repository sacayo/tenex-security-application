"""Shapes for the model-written brief.

The narrative endpoints return one ``NarrativeResponse``; the frontend renders
it 1:1, so update ``spec.md`` and ``web/lib/types.ts`` together. Field names on
``NarrativeSections`` are the model's JSON-schema contract
(``app.service.narrative.JSON_SCHEMA``).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

NarrativeStatus = Literal["pending", "ready", "failed"]
RiskLevel = Literal["none", "low", "medium", "high"]


class NarrativeSections(BaseModel):
    """What the model writes. Kept small so it stays cheap and checkable."""

    headline: str = Field(max_length=200)
    overview: str = Field(max_length=1200)
    key_findings: list[str] = Field(max_length=6)
    recommended_actions: list[str] = Field(max_length=6)


class NarrativeResponse(BaseModel):
    """One upload's narrative state and, when ready, its sections."""

    upload_id: int
    status: NarrativeStatus
    # Computed in Python from anomaly severities - never by the model.
    risk_level: RiskLevel
    sections: NarrativeSections | None = None
    model: str | None = None
    prompt_version: str | None = None
    generated_at: datetime | None = None
    error_message: str | None = None
