"""Request/response wire models for the HTTP API.

These are the bodies clients send (and the small ack payloads they get
back) — everything else on the wire lives in the sibling modules
(``session``, ``message``, ``event``).
"""

from __future__ import annotations

from pydantic import Field

from skene.schema.base import WireModel
from skene.schema.message import Message, Part


class SessionCreateRequest(WireModel):
    agent: str = "skene"
    parent_id: str | None = None
    title: str | None = None


class PromptRequest(WireModel):
    """Body of ``POST /session/{id}/message``."""

    text: str = Field(min_length=1)


class MessageWithParts(WireModel):
    """One message plus its parts, as returned by ``GET /session/{id}/message``."""

    info: Message
    parts: list[Part] = Field(default_factory=list)


class JourneyAnalyseRequest(WireModel):
    """Body of ``POST /journey/analyse`` — the v1-compat canned analysis.

    Mirrors the ``skene analyse-journey`` CLI flags. ``db_url`` is used for
    live introspection only and is never persisted or echoed back — the
    stored session records a redacted display form.
    """

    path: str | None = None
    schema_dir: str | None = None
    db_url: str | None = None
    product_name: str | None = None
    output: str | None = None
    schema_max_turns: int = Field(default=150, ge=1, le=500)
    code_max_turns: int = Field(default=200, ge=1, le=500)
    classify_concurrency: int = Field(default=8, ge=1, le=64)
    specialize: bool = True


class JourneyAnalyseAccepted(WireModel):
    """Ack for ``POST /journey/analyse``: the run proceeds async in this session."""

    session_id: str
