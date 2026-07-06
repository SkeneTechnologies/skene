"""The agent registry, read-only."""

from __future__ import annotations

from fastapi import APIRouter

from skene.schema import AgentInfo
from skene.server.deps import Services

router = APIRouter(tags=["agent"])


@router.get("/agent", response_model=list[AgentInfo])
async def list_agents(services: Services) -> list[AgentInfo]:
    """Registered agents: primaries are promptable, subagents are reachable
    only through a primary agent's ``task`` tool."""
    return services.registry.info()
