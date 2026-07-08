"""Permission ask/answer wire models (phase 5).

A tool that wants to do something guarded (e.g. write to a live database)
asks for permission mid-run: the run pauses on the ask, clients see a
``permission.asked`` event, and one of them answers via
``POST /session/{id}/permissions/{permID}``. There are no rulesets yet —
every ask goes to the client and is answered once.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from skene.schema.base import WireModel

PermissionStatus = Literal["pending", "allowed", "denied"]

PermissionReply = Literal["allow", "deny"]


class PermissionRequest(WireModel):
    """One pending or answered ask, as persisted and streamed."""

    id: str
    session_id: str
    tool: str
    title: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: PermissionStatus = "pending"
    created: int
    answered: int | None = None


class PermissionAnswer(WireModel):
    """Body of ``POST /session/{id}/permissions/{permID}``."""

    reply: PermissionReply
