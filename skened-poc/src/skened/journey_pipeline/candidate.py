"""Intermediate milestone emitted by the extractor before classification.

Stage assignment happens later, so ``stage_id`` is nullable here. The final
``Milestone`` is built in ``assemble`` once everything has been classified.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..journey import ID_PATTERN, Evidence


class CandidateMilestone(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposed_id: str = Field(pattern=ID_PATTERN)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    evidence: list[Evidence] = Field(min_length=1)
    tracked_event: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    # Filled in by the classify step.
    stage_id: str | None = None
