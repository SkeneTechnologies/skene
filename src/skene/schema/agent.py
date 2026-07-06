"""Agent registry wire model."""

from __future__ import annotations

from typing import Literal

from skene.schema.base import WireModel

AgentMode = Literal["primary", "subagent"]


class AgentInfo(WireModel):
    """A registered agent as exposed by ``GET /agent``.

    ``primary`` agents are user-selectable; ``subagent`` agents are only
    reachable through a primary agent's ``task`` tool.
    """

    name: str
    mode: AgentMode
    description: str | None = None
    model: str | None = None
    hidden: bool = False
