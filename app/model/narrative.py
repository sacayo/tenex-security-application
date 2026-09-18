"""Narrative shapes: the LLM-written brief for one upload.

POST/GET /api/uploads/{id}/narrative return one `NarrativeResponse`. The
frontend (`web/components/NarrativeCard.tsx`) renders these shapes 1:1 -
if you change them, update spec.md and `web/lib/types.ts` together.

`NarrativeSections` doubles as the JSON schema the model is constrained to
(see `app.service.narrative.JSON_SCHEMA`), so field names here ARE the
prompt contract.
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
    upload_id: int
    status: NarrativeStatus
    # Computed in Python from anomaly severities - never by the model.
    risk_level: RiskLevel
    sections: NarrativeSections | None = None
    model: str | None = None
    prompt_version: str | None = None
    generated_at: datetime | None = None
    error_message: str | None = None
