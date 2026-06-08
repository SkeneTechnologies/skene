"""Daemon state models: projects, branches, analysis runs.

These describe the daemon's *control-plane* state (what is registered, what has been
analyzed) and are distinct from the ``Journey`` artifact (the analysis output).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class RunKind(str, Enum):
    """Kind of analysis run. Only ``branch`` is implemented in this slice; ``drift`` and
    ``gap`` are reserved so the storage/run schema already accommodates them."""

    branch = "branch"
    drift = "drift"
    gap = "gap"


class Project(BaseModel):
    id: str
    name: str
    path: str
    default_branch: str
    github_remote: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class AnalysisRun(BaseModel):
    id: str
    project_id: str
    kind: RunKind = RunKind.branch
    branch: str
    commit: str
    status: JobStatus = JobStatus.queued
    created_at: datetime = Field(default_factory=utcnow)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    journey_path: str | None = None


class BranchInfo(BaseModel):
    """A live git branch merged with its latest analysis state from the DB."""

    name: str
    head_commit: str
    is_current: bool = False
    is_default: bool = False
    last_analyzed_commit: str | None = None
    last_commit_at: datetime | None = None  # last-commit date, for recency sorting
    status: JobStatus | None = None
    up_to_date: bool = False  # True when last_analyzed_commit == head_commit and succeeded
