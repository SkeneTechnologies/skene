"""The agent registry: which agents exist and what they are.

Pure metadata (name, mode, instructions, turn budget) — binding an agent
to its toolset happens where the run context lives
(:mod:`skene.core.tasks`), because subagent toolsets need per-run inputs
(repo root, schema index). The ``task`` tool builds its own description
from :meth:`AgentRegistry.subagents`, so registering a new subagent makes
it reachable without touching the main agent's prompt (opencode's
``describeTask`` pattern).

Per-agent model overrides ride on :attr:`AgentDef.model` and surface in
``GET /agent``; none of the built-in agents set one yet — the run still
uses the service-wide LLM factory.
"""

from __future__ import annotations

from dataclasses import dataclass

from skene.analyzers.journey.code_agent import CODE_AGENT_INSTRUCTIONS
from skene.analyzers.journey.schema_agent import SCHEMA_AGENT_INSTRUCTIONS
from skene.schema import AgentInfo, AgentMode

MAIN_AGENT_INSTRUCTIONS = """\
You are skene's main analysis agent. You orchestrate specialist subagents
to build the product's feature map, then produce the final journey.yaml
artifact.

How to work:
1. Read the request to see which evidence sources are available (a code
   repository, a database schema, or both).
2. Use the `task` tool to spawn one subagent per available source. Make
   ALL independent task calls in a single turn — they run in parallel.
3. Each task result reports how many features the subagent emitted. For
   a real product, fewer than ~10 features in total usually means the
   evidence was under-explored: re-run that subagent once with a sharper
   focus prompt before moving on.
4. When evidence gathering is done, call `synthesize_journey`. It merges
   the emitted features into the feature map (features.yaml),
   synthesizes user-journey milestones from it, assembles the journey,
   and writes journey.yaml.
5. Reply with a short summary of the journey and stop.

Rules:
- Never invent features yourself — only subagents gather evidence.
- Do not call synthesize_journey before at least one task has completed
  successfully.
- If a subagent fails or an evidence source is unavailable, continue
  with the sources you do have.
"""


@dataclass(frozen=True)
class AgentDef:
    """One registered agent. ``instructions`` is its system prompt."""

    name: str
    mode: AgentMode
    description: str
    instructions: str
    max_turns: int = 20
    model: str | None = None

    def info(self) -> AgentInfo:
        return AgentInfo(name=self.name, mode=self.mode, description=self.description, model=self.model)


DEFAULT_AGENTS: tuple[AgentDef, ...] = (
    AgentDef(
        name="skene",
        mode="primary",
        description="Main analysis agent: orchestrates subagents, builds the feature map, and assembles journey.yaml.",
        instructions=MAIN_AGENT_INSTRUCTIONS,
        max_turns=30,
    ),
    AgentDef(
        name="code",
        mode="subagent",
        description=("Explores the product's code repository and emits product features."),
        instructions=CODE_AGENT_INSTRUCTIONS,
        max_turns=200,
    ),
    AgentDef(
        name="schema",
        mode="subagent",
        description=("Explores the product's database schema and emits product features."),
        instructions=SCHEMA_AGENT_INSTRUCTIONS,
        max_turns=150,
    ),
)


class AgentRegistry:
    def __init__(self, agents: tuple[AgentDef, ...] = DEFAULT_AGENTS) -> None:
        self._agents: dict[str, AgentDef] = {}
        for agent in agents:
            if agent.name in self._agents:
                raise ValueError(f"duplicate agent name: {agent.name}")
            self._agents[agent.name] = agent

    def get(self, name: str) -> AgentDef | None:
        return self._agents.get(name)

    def subagents(self) -> list[AgentDef]:
        return [a for a in self._agents.values() if a.mode == "subagent"]

    def list(self) -> list[AgentDef]:
        return list(self._agents.values())

    def info(self) -> list[AgentInfo]:
        return [a.info() for a in self._agents.values()]
