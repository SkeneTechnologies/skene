"""Message and part wire models.

Shapes follow opencode's tagged-union message/part design
(``packages/schema/src/session-message.ts``): a message is discriminated by
``role``, its content is a list of parts discriminated by ``type``, and tool
parts carry a ``ToolState`` discriminated by ``status`` that transitions
``pending -> running -> completed | error``. Clients render parts
incrementally as ``part.updated`` events stream in.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import Field

from skene.schema.base import WireModel

# ---------------------------------------------------------------------------
# Tool state
# ---------------------------------------------------------------------------


class ToolStatePending(WireModel):
    status: Literal["pending"] = "pending"


class ToolStateRunning(WireModel):
    status: Literal["running"] = "running"
    input: dict[str, Any] = Field(default_factory=dict)
    title: str | None = None
    started: int | None = None  # epoch ms


class ToolStateCompleted(WireModel):
    status: Literal["completed"] = "completed"
    input: dict[str, Any] = Field(default_factory=dict)
    output: str = ""
    title: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    started: int | None = None
    ended: int | None = None


class ToolStateError(WireModel):
    status: Literal["error"] = "error"
    input: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    started: int | None = None
    ended: int | None = None


ToolState = Annotated[
    Union[ToolStatePending, ToolStateRunning, ToolStateCompleted, ToolStateError],
    Field(discriminator="status"),
]

# ---------------------------------------------------------------------------
# Parts
# ---------------------------------------------------------------------------


class _BasePart(WireModel):
    id: str
    session_id: str
    message_id: str


class TextPart(_BasePart):
    type: Literal["text"] = "text"
    text: str


class ReasoningPart(_BasePart):
    type: Literal["reasoning"] = "reasoning"
    text: str


class ToolPart(_BasePart):
    type: Literal["tool"] = "tool"
    tool: str
    call_id: str
    state: ToolState


class MilestonePart(_BasePart):
    """A candidate milestone emitted by an analysis agent's ``emit_milestone``.

    ``milestone`` is the serialized
    :class:`skene.analyzers.journey.candidate.CandidateMilestone`. Kept as a
    plain dict until phase 3 moves the analyzer models onto this package —
    at which point this becomes a typed reference (single source of truth).
    """

    type: Literal["milestone"] = "milestone"
    milestone: dict[str, Any]


class ArtifactPart(_BasePart):
    """A file the run produced (e.g. ``journey.yaml``)."""

    type: Literal["artifact"] = "artifact"
    path: str
    title: str | None = None
    summary: str | None = None


Part = Annotated[
    Union[TextPart, ReasoningPart, ToolPart, MilestonePart, ArtifactPart],
    Field(discriminator="type"),
]

# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


class TokenUsage(WireModel):
    input: int = 0
    output: int = 0


class _BaseMessage(WireModel):
    id: str
    session_id: str
    created: int  # epoch ms


class UserMessage(_BaseMessage):
    role: Literal["user"] = "user"


class AssistantMessage(_BaseMessage):
    role: Literal["assistant"] = "assistant"
    agent: str
    provider: str | None = None
    model: str | None = None
    tokens: TokenUsage | None = None
    finish: str | None = None  # "no_tool_calls" | "max_turns" | "aborted" | "error"
    error: str | None = None


class SyntheticMessage(_BaseMessage):
    """Server-injected content, e.g. a subagent result surfaced to its parent."""

    role: Literal["synthetic"] = "synthetic"


Message = Annotated[
    Union[UserMessage, AssistantMessage, SyntheticMessage],
    Field(discriminator="role"),
]
