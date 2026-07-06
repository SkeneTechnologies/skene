"""Wire-format models shared by the server, CLI, and TUI clients.

This package is the single source of truth for everything that crosses the
HTTP/SSE boundary (see ``docs/design/backend-server.md``). FastAPI derives
the OpenAPI spec from these models, and client SDKs are generated from that
spec — so changes here are wire-format changes.

JSON uses camelCase (``session.parentId``); Python uses snake_case. All
models accept both on input.
"""

from skene.schema.agent import AgentInfo, AgentMode
from skene.schema.event import (
    Event,
    MessageCreated,
    MessageUpdated,
    PartCreated,
    PartUpdated,
    ServerConnected,
    ServerHeartbeat,
    SessionCreated,
    SessionError,
    SessionIdle,
    SessionUpdated,
)
from skene.schema.ids import new_id
from skene.schema.message import (
    ArtifactPart,
    AssistantMessage,
    Message,
    MilestonePart,
    Part,
    ReasoningPart,
    SyntheticMessage,
    TextPart,
    TokenUsage,
    ToolPart,
    ToolState,
    ToolStateCompleted,
    ToolStateError,
    ToolStatePending,
    ToolStateRunning,
    UserMessage,
)
from skene.schema.request import (
    JourneyAnalyseAccepted,
    JourneyAnalyseRequest,
    MessageWithParts,
    PromptRequest,
    SessionCreateRequest,
)
from skene.schema.session import Project, Session, SessionStatus

__all__ = [
    "AgentInfo",
    "AgentMode",
    "ArtifactPart",
    "AssistantMessage",
    "Event",
    "JourneyAnalyseAccepted",
    "JourneyAnalyseRequest",
    "Message",
    "MessageCreated",
    "MessageUpdated",
    "MessageWithParts",
    "MilestonePart",
    "Part",
    "PartCreated",
    "PartUpdated",
    "Project",
    "PromptRequest",
    "ReasoningPart",
    "ServerConnected",
    "ServerHeartbeat",
    "Session",
    "SessionCreateRequest",
    "SessionCreated",
    "SessionError",
    "SessionIdle",
    "SessionStatus",
    "SessionUpdated",
    "SyntheticMessage",
    "TextPart",
    "TokenUsage",
    "ToolPart",
    "ToolState",
    "ToolStateCompleted",
    "ToolStateError",
    "ToolStatePending",
    "ToolStateRunning",
    "UserMessage",
    "new_id",
]
