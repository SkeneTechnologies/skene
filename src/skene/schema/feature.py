"""Feature wire models.

These used to live in ``skene.analyzers.journey`` (phase-1 loose end);
they moved here in phase 3 because features now cross the wire as
``FeaturePart`` payloads. The analyzer modules re-export them, so engine
code keeps importing from its usual homes.

``Feature`` is one entry of the *feature map*: a user-facing capability
with evidence, emitted live by the code/schema subagents' ``emit_feature``
tool. Journey milestones do not exist at this level — the synthesis step
inside ``synthesize_journey`` composes them from groups of features, and
the final ``Milestone`` only exists inside ``journey.yaml``
(:mod:`skene.analyzers.journey.models`).
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from skene.schema.base import WireModel

# Lowercase snake_case identifier, must start with a letter. Shared with
# the journey.yaml models in skene.analyzers.journey.models.
ID_PATTERN = r"^[a-z][a-z0-9_]*$"


class EvidenceSource(str, Enum):
    code = "code"
    db = "db"
    config = "config"


class Evidence(WireModel):
    """A pointer back to the code path or DB table that justifies a feature."""

    source: EvidenceSource
    reason: str = Field(min_length=1)
    path: str | None = Field(
        default=None,
        description="Required when source == 'code'. File path inside the repo.",
    )
    table: str | None = Field(
        default=None,
        description="Required when source == 'db'. Table or collection name.",
    )

    @model_validator(mode="after")
    def check_source_fields(self) -> "Evidence":
        if self.source == EvidenceSource.code and not self.path:
            raise ValueError("evidence.source='code' requires 'path'")
        if self.source == EvidenceSource.db and not self.table:
            raise ValueError("evidence.source='db' requires 'table'")
        return self


class Feature(WireModel):
    """A product feature emitted by a subagent — one feature-map entry."""

    proposed_id: str = Field(pattern=ID_PATTERN)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    evidence: list[Evidence] = Field(min_length=1)
    tracked_event: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
