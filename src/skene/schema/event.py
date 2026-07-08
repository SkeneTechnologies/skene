"""Server-sent event wire models.

Every event is ``{id, type, properties}`` on the wire (opencode's SSE
shape). ``Event`` is the discriminated union streamed from ``GET /event``.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field

from skene.schema.base import WireModel
from skene.schema.ids import new_id
from skene.schema.message import Message, Part
from skene.schema.permission import PermissionRequest
from skene.schema.session import Session


def _event_id() -> str:
    return new_id("evt")


class _BaseEvent(WireModel):
    id: str = Field(default_factory=_event_id)


# --- server lifecycle ------------------------------------------------------


class _Empty(WireModel):
    pass


class ServerConnected(_BaseEvent):
    type: Literal["server.connected"] = "server.connected"
    properties: _Empty = Field(default_factory=_Empty)


class ServerHeartbeat(_BaseEvent):
    type: Literal["server.heartbeat"] = "server.heartbeat"
    properties: _Empty = Field(default_factory=_Empty)


# --- sessions ---------------------------------------------------------------


class _SessionProps(WireModel):
    session: Session


class SessionCreated(_BaseEvent):
    type: Literal["session.created"] = "session.created"
    properties: _SessionProps


class SessionUpdated(_BaseEvent):
    type: Literal["session.updated"] = "session.updated"
    properties: _SessionProps


class SessionIdle(_BaseEvent):
    type: Literal["session.idle"] = "session.idle"
    properties: _SessionProps


class _SessionErrorProps(WireModel):
    session: Session
    error: str


class SessionError(_BaseEvent):
    type: Literal["session.error"] = "session.error"
    properties: _SessionErrorProps


# --- messages & parts -------------------------------------------------------


class _MessageProps(WireModel):
    message: Message


class MessageCreated(_BaseEvent):
    type: Literal["message.created"] = "message.created"
    properties: _MessageProps


class MessageUpdated(_BaseEvent):
    type: Literal["message.updated"] = "message.updated"
    properties: _MessageProps


class _PartProps(WireModel):
    part: Part
    # For streaming text parts: the appended suffix since the last event, so
    # clients can render deltas without diffing the full part.
    delta: str | None = None


class PartCreated(_BaseEvent):
    type: Literal["part.created"] = "part.created"
    properties: _PartProps


class PartUpdated(_BaseEvent):
    type: Literal["part.updated"] = "part.updated"
    properties: _PartProps


# --- permissions --------------------------------------------------------------


class _PermissionProps(WireModel):
    request: PermissionRequest


class PermissionAsked(_BaseEvent):
    type: Literal["permission.asked"] = "permission.asked"
    properties: _PermissionProps


class PermissionAnswered(_BaseEvent):
    type: Literal["permission.answered"] = "permission.answered"
    properties: _PermissionProps


Event = Annotated[
    Union[
        ServerConnected,
        ServerHeartbeat,
        SessionCreated,
        SessionUpdated,
        SessionIdle,
        SessionError,
        MessageCreated,
        MessageUpdated,
        PartCreated,
        PartUpdated,
        PermissionAsked,
        PermissionAnswered,
    ],
    Field(discriminator="type"),
]
