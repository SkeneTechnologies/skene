"""Intermediate milestone type emitted by the schema and code agents.

Stage assignment happens in a later step, so ``stage_id`` is nullable on
this type. The final :class:`skene.analyzers.journey.models.Milestone` is
built in :mod:`skene.analyzers.journey.assemble` once everything has been
classified.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from skene.analyzers.journey.models import ID_PATTERN, Evidence


class CandidateMilestone(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposed_id: str = Field(pattern=ID_PATTERN)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    evidence: list[Evidence] = Field(min_length=1)
    tracked_event: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    # Filled in by Step 4 (classify).
    stage_id: str | None = None
