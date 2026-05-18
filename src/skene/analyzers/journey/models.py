"""Pydantic models for the journey.yaml schema.

These models are the source of truth for the final ``journey.yaml`` artifact
emitted by ``skene analyse-journey``. They are validated end-to-end before
the file is written, so any pipeline bug that produces an invalid Journey
fails loudly instead of writing garbage.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EvidenceSource(str, Enum):
    code = "code"
    db = "db"
    config = "config"


class TriggerType(str, Enum):
    email = "email"
    scheduled = "scheduled"
    webhook = "webhook"
    event_bus = "event_bus"
    unknown = "unknown"


class ConnectorStyle(str, Enum):
    solid = "solid"
    dashed = "dashed"
    dotted = "dotted"


class KpiUnit(str, Enum):
    percentage = "percentage"
    count = "count"
    duration_days = "duration_days"
    duration_hours = "duration_hours"
    ratio = "ratio"
    currency = "currency"


# Lowercase snake_case identifier, must start with a letter.
ID_PATTERN = r"^[a-z][a-z0-9_]*$"

# "<stage_id>.<milestone_id>"
STAGE_REF_PATTERN = r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$"

# Connectors can target a real milestone OR the literal string "unknown".
CONNECTOR_TARGET_PATTERN = r"^([a-z][a-z0-9_]*\.[a-z][a-z0-9_]*|unknown)$"

# Layer IDs are L1, L2, L3, ...
LAYER_ID_PATTERN = r"^L[0-9]+$"


class Evidence(BaseModel):
    """A pointer back to the code path or DB table that justifies a milestone."""

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


class KpiDerivation(BaseModel):
    numerator_table: str | None = None
    denominator_table: str | None = None
    numerator_event: str | None = None
    denominator_event: str | None = None
    notes: str | None = None


class Kpi(BaseModel):
    id: str = Field(pattern=ID_PATTERN)
    name: str = Field(min_length=1)
    target: str | None = Field(default=None)
    unit: KpiUnit
    derived_from: KpiDerivation | None = None


class Milestone(BaseModel):
    id: str = Field(pattern=ID_PATTERN)
    order: int = Field(ge=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    evidence: list[Evidence] = Field(min_length=1)
    tracked_event: str | None = Field(default=None)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class Stage(BaseModel):
    id: str = Field(pattern=ID_PATTERN)
    order: int = Field(ge=1)
    name: str = Field(min_length=1)
    subtitle: str | None = None
    milestones: list[Milestone] = Field(min_length=1)
    kpis: list[Kpi] = Field(default_factory=list)

    @field_validator("milestones")
    @classmethod
    def unique_milestone_ids(cls, v: list[Milestone]) -> list[Milestone]:
        ids = [m.id for m in v]
        if len(ids) != len(set(ids)):
            raise ValueError("milestone ids must be unique within a stage")
        return v

    @field_validator("milestones")
    @classmethod
    def unique_milestone_orders(cls, v: list[Milestone]) -> list[Milestone]:
        orders = [m.order for m in v]
        if len(orders) != len(set(orders)):
            raise ValueError("milestone orders must be unique within a stage")
        return v

    @field_validator("kpis")
    @classmethod
    def unique_kpi_ids(cls, v: list[Kpi]) -> list[Kpi]:
        ids = [k.id for k in v]
        if len(ids) != len(set(ids)):
            raise ValueError("kpi ids must be unique within a stage")
        return v


class Layer(BaseModel):
    id: str = Field(pattern=LAYER_ID_PATTERN)
    name: str = Field(min_length=1)
    spans_stages: list[str] = Field(min_length=1)


class Connector(BaseModel):
    """A cross-stage link: one milestone's completion triggers another."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(pattern=ID_PATTERN)
    from_: str = Field(alias="from", pattern=STAGE_REF_PATTERN)
    to: str = Field(pattern=CONNECTOR_TARGET_PATTERN)
    label: str = Field(min_length=1)
    trigger_type: TriggerType
    style: ConnectorStyle = ConnectorStyle.dashed
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence: list[Evidence] = Field(min_length=1)


class Product(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    generated_at: datetime
    source_commit: str | None = None


class Journey(BaseModel):
    """The whole document."""

    model_config = ConfigDict(populate_by_name=True)

    product: Product
    layers: list[Layer] = Field(default_factory=list)
    stages: list[Stage] = Field(min_length=1)
    connectors: list[Connector] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_stage_ids_unique(self) -> "Journey":
        ids = [s.id for s in self.stages]
        if len(ids) != len(set(ids)):
            raise ValueError("stage ids must be unique")
        return self

    @model_validator(mode="after")
    def check_stage_orders_unique(self) -> "Journey":
        orders = [s.order for s in self.stages]
        if len(orders) != len(set(orders)):
            raise ValueError("stage orders must be unique")
        return self

    @model_validator(mode="after")
    def check_layer_ids_unique(self) -> "Journey":
        ids = [layer.id for layer in self.layers]
        if len(ids) != len(set(ids)):
            raise ValueError("layer ids must be unique")
        return self

    @model_validator(mode="after")
    def check_layers_reference_real_stages(self) -> "Journey":
        stage_ids = {s.id for s in self.stages}
        for layer in self.layers:
            missing = set(layer.spans_stages) - stage_ids
            if missing:
                raise ValueError(f"layer {layer.id} references unknown stages: {sorted(missing)}")
        return self

    @model_validator(mode="after")
    def check_connector_ids_unique(self) -> "Journey":
        ids = [c.id for c in self.connectors]
        if len(ids) != len(set(ids)):
            raise ValueError("connector ids must be unique")
        return self

    @model_validator(mode="after")
    def check_connectors_reference_real_milestones(self) -> "Journey":
        valid_refs = {f"{s.id}.{m.id}" for s in self.stages for m in s.milestones}
        for c in self.connectors:
            if c.from_ not in valid_refs:
                raise ValueError(f"connector {c.id}: 'from' {c.from_!r} does not match any milestone")
            if c.to != "unknown" and c.to not in valid_refs:
                raise ValueError(f"connector {c.id}: 'to' {c.to!r} does not match any milestone")
        return self
