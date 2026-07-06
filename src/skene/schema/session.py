"""Project and session wire models."""

from __future__ import annotations

from typing import Literal

from skene.schema.base import WireModel

SessionStatus = Literal["idle", "running", "error"]


class Project(WireModel):
    """A workspace directory the server has analyzed."""

    id: str
    directory: str
    name: str | None = None


class Session(WireModel):
    """One agent conversation.

    Subagent runs are child sessions: ``parent_id`` points at the session
    whose ``task`` tool spawned them.
    """

    id: str
    project_id: str
    parent_id: str | None = None
    agent: str
    title: str | None = None
    status: SessionStatus = "idle"
    created: int  # epoch ms
    updated: int  # epoch ms
